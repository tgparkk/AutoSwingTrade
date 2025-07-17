"""
매매 신호 관리자 클래스

매매 신호 생성과 실행을 담당하는 클래스입니다.
"""
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from utils.logger import setup_logger
from utils.korean_time import now_kst, safe_datetime_subtract
from core.enums import SignalType
from core.models import TradingConfig, Position, TradingSignal, TradeRecord
from trading.candidate_screener import PatternResult
from core.enums import PatternType
from trading.order_manager import OrderManager
from trading.position_manager import PositionManager
from api.kis_api_manager import AccountInfo, OrderResult


class TradingSignalManager:
    """매매 신호 관리자 클래스"""
    
    def __init__(self, 
                 config: TradingConfig,
                 order_manager: OrderManager,
                 position_manager: PositionManager,
                 message_queue: queue.Queue):
        """
        매매 신호 관리자 초기화
        
        Args:
            config: 매매 설정
            order_manager: 주문 관리자
            position_manager: 포지션 관리자
            message_queue: 메시지 큐
        """
        self.logger = setup_logger(__name__)
        self.config = config
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.message_queue = message_queue
        
        # 매매 기록
        self.trade_history: List[TradeRecord] = []
        
        self.logger.info("✅ TradingSignalManager 초기화 완료")
    
    def generate_trading_signals(self, 
                               candidate_results: List[PatternResult],
                               positions: Dict[str, Position],
                               account_info: Optional[AccountInfo],
                               pending_orders: Optional[Dict[str, Any]] = None) -> List[TradingSignal]:
        """
        매매 신호 생성 (캔들패턴 기반)
        
        Args:
            candidate_results: 매수후보 종목 결과
            positions: 현재 포지션
            account_info: 계좌 정보
            pending_orders: 대기 중인 주문 목록 (중복 신호 방지용)
            
        Returns:
            List[TradingSignal]: 생성된 매매 신호 목록
        """
        signals = []

        now_time = now_kst()
        
        try:
            # 대기 중인 주문이 있는 종목들 추출
            pending_buy_stocks = set()
            pending_sell_stocks = set()
            
            if pending_orders: 
                for order in pending_orders.values():
                    if hasattr(order, 'signal_type') and hasattr(order, 'stock_code'):
                        if order.signal_type == SignalType.BUY:
                            pending_buy_stocks.add(order.stock_code)
                        elif order.signal_type == SignalType.SELL:
                            pending_sell_stocks.add(order.stock_code)
                
                if pending_buy_stocks or pending_sell_stocks:
                    self.logger.debug(f"🔒 대기 중인 주문 - 매수: {len(pending_buy_stocks)}건, 매도: {len(pending_sell_stocks)}건")
            
            # 매수 신호 생성 (후보 종목이 있는 경우에만)
            if candidate_results:
                self.logger.info(f"📊 매수 후보 종목 {len(candidate_results)}개 분석 중...")
                
                # 상위 10개 후보 종목에 대해 매수 신호 생성
                processed_count = 0
                for candidate in candidate_results[:10]:
                    processed_count += 1

                    if 10 < now_time.hour:
                        # 오전 10시이전에만 실행
                        continue
                    
                    # 이미 보유한 종목은 제외
                    if candidate.stock_code in positions:
                        self.logger.debug(f"⏸️ 이미 보유 중인 종목 제외: {candidate.stock_name}")
                        continue
                    
                    # 🔒 이미 매수 주문이 대기 중인 종목은 제외
                    if candidate.stock_code in pending_buy_stocks:
                        self.logger.debug(f"⏸️ 매수 주문 대기 중인 종목 제외: {candidate.stock_name}")
                        continue
                    
                    # 🔥 강화된 패턴별 최소 신뢰도 조건 (스크리너와 동일한 기준)
                    pattern_min_confidence = {
                        PatternType.MORNING_STAR: 85.0,        # 샛별: 85% 이상
                        PatternType.THREE_WHITE_SOLDIERS: 80.0, # 세 백병: 80% 이상
                        PatternType.ABANDONED_BABY: 80.0,      # 버려진 아기: 80% 이상
                        PatternType.BULLISH_ENGULFING: 75.0,   # 상승장악형: 75% 이상
                        PatternType.HAMMER: 70.0               # 망치형: 70% 이상
                    }
                    
                    min_confidence = pattern_min_confidence.get(candidate.pattern_type, 75.0)
                    
                    if candidate.confidence < min_confidence:
                        self.logger.debug(f"⏸️ 강화된 신뢰도 부족으로 제외: {candidate.stock_name} "
                                        f"(신뢰도: {candidate.confidence:.1f}% < 최소: {min_confidence}%)")
                        continue
                    
                    # 매수 수량 계산 (계좌 전체 금액의 10~20% 범위)
                    if account_info:
                        total_value = account_info.total_value
                        
                        # 🎯 강화된 신뢰도 기반 투자 비율 결정 (최소 신뢰도 ~ 100%)
                        confidence_ratio = candidate.confidence / 100.0
                        min_confidence_ratio = min_confidence / 100.0
                        
                        # 패턴별 최소 신뢰도부터 100%까지의 범위에서 투자 비율 계산
                        if confidence_ratio > min_confidence_ratio:
                            normalized_confidence = (confidence_ratio - min_confidence_ratio) / (1.0 - min_confidence_ratio)
                            position_ratio = self.config.min_position_ratio + (
                                (self.config.max_position_ratio - self.config.min_position_ratio) * normalized_confidence
                            )
                        else:
                            position_ratio = self.config.min_position_ratio  # 최소 투자 비율
                        
                        # 투자 금액 계산
                        target_amount = total_value * position_ratio
                        
                        # 가용 자금 확인
                        available_amount = account_info.available_amount
                        investment_amount = min(target_amount, available_amount)
                        
                        # 매수 수량 계산
                        quantity = int(investment_amount / candidate.current_price)
                        
                        if quantity > 0:
                            signal = TradingSignal(
                                stock_code=candidate.stock_code,
                                stock_name=candidate.stock_name,
                                signal_type=SignalType.BUY,
                                price=candidate.current_price,
                                quantity=quantity,
                                reason=f"캔들패턴 매수 신호 - {candidate.pattern_type.value} "
                                       f"(신뢰도: {candidate.confidence:.1f}%, 투자비율: {position_ratio:.1%})",
                                confidence=candidate.confidence / 100.0,  # 0.0 ~ 1.0으로 변환
                                timestamp=now_kst(),
                                stop_loss_price=candidate.stop_loss,
                                take_profit_price=candidate.target_price,
                                metadata={
                                    'pattern_type': candidate.pattern_type,
                                    'market_cap_type': candidate.market_cap_type.value,
                                    'pattern_strength': candidate.pattern_strength,
                                    'volume_ratio': candidate.volume_ratio
                                }
                            )
                            signals.append(signal)
                            
                            self.logger.info(f"✅ 매수 신호 생성: {candidate.stock_name} "
                                           f"(신뢰도: {candidate.confidence:.1f}%, 수량: {quantity}주)")
                        else:
                            self.logger.debug(f"⏸️ 매수 수량 부족으로 제외: {candidate.stock_name} "
                                            f"(투자금액: {investment_amount:,.0f}원, 현재가: {candidate.current_price:,.0f}원)")
                    else:
                        self.logger.warning("⚠️ 계좌 정보가 없어 매수 신호 생성 불가")
                
                if signals:
                    self.logger.debug(f"✅ 총 {len(signals)}개 매수 신호 생성 완료")
                else:
                    self.logger.debug(f"📊 매수 신호 생성 결과: 0개 (분석 종목: {processed_count}개)")
            else:
                self.logger.debug("📊 매수 후보 종목이 없습니다")
            
            # 기존 포지션에 대한 패턴별 차별화 매도 신호 생성
            for position in positions.values():
                # 🔒 이미 매도 주문이 대기 중인 종목은 제외
                if position.stock_code in pending_sell_stocks:
                    self.logger.debug(f"⏸️ 매도 주문 대기 중인 종목 제외: {position.stock_name}")
                    continue
                
                # 🎯 패턴별 차별화 매도 조건 확인
                if position.pattern_type:
                    pattern_exit_signal = self._check_pattern_based_exit(position)
                    if pattern_exit_signal:
                        signals.append(pattern_exit_signal)
                        continue  # 패턴 기반 신호가 생성되면 기본 로직 스킵
                
                # 🕐 시간 기반 매도 조건 확인 (최우선)
                if self.config.enable_time_based_exit:
                    holding_days = safe_datetime_subtract(now_kst(), position.entry_time).days
                    
                    # 1. 최대 보유 기간 초과 시 강제 매도
                    if holding_days >= self.config.max_holding_days:
                        signal = TradingSignal(
                            stock_code=position.stock_code,
                            stock_name=position.stock_name,
                            signal_type=SignalType.SELL,
                            price=position.current_price,
                            quantity=position.quantity,
                            reason=f"최대 보유기간 초과 매도 - {holding_days}일 보유 "
                                   f"(최대: {self.config.max_holding_days}일)",
                            confidence=1.0,
                            timestamp=now_kst()
                        )
                        signals.append(signal)
                        continue
                    
                    # 2. 횡보 구간 매도 (손익률이 임계값 내에서 일정 기간 유지)
                    elif (holding_days >= self.config.sideways_exit_days and 
                          abs(position.profit_loss_rate) <= self.config.sideways_threshold):
                        signal = TradingSignal(
                            stock_code=position.stock_code,
                            stock_name=position.stock_name,
                            signal_type=SignalType.SELL,
                            price=position.current_price,
                            quantity=position.quantity,
                            reason=f"횡보 구간 매도 - {holding_days}일 보유, "
                                   f"손익률: {position.profit_loss_rate:.2f}% "
                                   f"(임계값: ±{self.config.sideways_threshold:.1%})",
                            confidence=0.8,
                            timestamp=now_kst()
                        )
                        signals.append(signal)
                        continue
                    
                    # 3. 부분 매도 (일정 기간 후 수익이 나고 있으면 부분 매도)
                    elif (holding_days >= self.config.partial_exit_days and 
                          position.profit_loss_rate > 0 and
                          not position.partial_sold):
                        partial_quantity = int(position.quantity * self.config.partial_exit_ratio)
                        if partial_quantity > 0:
                            signal = TradingSignal(
                                stock_code=position.stock_code,
                                stock_name=position.stock_name,
                                signal_type=SignalType.SELL,
                                price=position.current_price,
                                quantity=partial_quantity,
                                reason=f"부분 매도 - {holding_days}일 보유, "
                                       f"수익률: {position.profit_loss_rate:.2f}% "
                                       f"({partial_quantity}주/{position.quantity}주)",
                                confidence=0.7,
                                timestamp=now_kst()
                            )
                            signals.append(signal)
                            # 부분 매도 플래그 설정 (중복 방지)
                            position.partial_sold = True
                            continue
                
                # 손절 조건 확인 (패턴 기반 손절가 활용)
                if (position.stop_loss_price and 
                    position.current_price <= position.stop_loss_price):
                    signal = TradingSignal(
                        stock_code=position.stock_code,
                        stock_name=position.stock_name,
                        signal_type=SignalType.SELL,
                        price=position.current_price,
                        quantity=position.quantity,
                        reason=f"패턴 기반 손절매 - 현재가: {position.current_price:,.0f}원, "
                               f"손절가: {position.stop_loss_price:,.0f}원",
                        confidence=1.0,  # 손절매는 신뢰도 100%
                        timestamp=now_kst()
                    )
                    signals.append(signal)
                    
                # 익절 조건 확인 (패턴 기반 목표가 활용)
                elif (position.take_profit_price and 
                      position.current_price >= position.take_profit_price):
                    signal = TradingSignal(
                        stock_code=position.stock_code,
                        stock_name=position.stock_name,
                        signal_type=SignalType.SELL,
                        price=position.current_price,
                        quantity=position.quantity,  # 전량 매도
                        reason=f"패턴 기반 익절매 - 현재가: {position.current_price:,.0f}원, "
                               f"목표가: {position.take_profit_price:,.0f}원",
                        confidence=1.0,  # 익절매는 신뢰도 100%
                        timestamp=now_kst()
                    )
                    signals.append(signal)
                    
                # 패턴 기반 손절/익절가가 없는 경우 기본 비율 사용 (하위 호환성)
                elif not position.stop_loss_price and not position.take_profit_price:
                    if position.profit_loss_rate <= -1.0:  # 1% 손실
                        signal = TradingSignal(
                            stock_code=position.stock_code,
                            stock_name=position.stock_name,
                            signal_type=SignalType.SELL,
                            price=position.current_price,
                            quantity=position.quantity,
                            reason=f"기본 손절매 - 손실률: {position.profit_loss_rate:.1f}%",
                            confidence=1.0,
                            timestamp=now_kst()
                        )
                        signals.append(signal)
                    elif position.profit_loss_rate >= 3.0:  # 3% 수익으로 보수적 조정
                        signal = TradingSignal(
                            stock_code=position.stock_code,
                            stock_name=position.stock_name,
                            signal_type=SignalType.SELL,
                            price=position.current_price,
                            quantity=position.quantity,
                            reason=f"기본 익절매 - 수익률: {position.profit_loss_rate:.1f}%",
                            confidence=1.0,
                            timestamp=now_kst()
                        )
                        signals.append(signal)
            
        except Exception as e:
            self.logger.error(f"❌ 매매 신호 생성 오류: {e}")
        
        return signals
    
    def generate_intraday_buy_signals(self, 
                                    candidate_results: List[PatternResult],
                                    positions: Dict[str, Position],
                                    account_info: Optional[AccountInfo],
                                    pending_orders: Optional[Dict[str, Any]] = None) -> List[TradingSignal]:
        """
        14:55 장중 스캔 후 즉시 매수 신호 생성 (실시간 현재가 적용)
        
        Args:
            candidate_results: 실시간 스캔 결과 (14:55 시점)
            positions: 현재 포지션
            account_info: 계좌 정보
            pending_orders: 대기 중인 주문 목록
            
        Returns:
            List[TradingSignal]: 즉시 매수 신호 목록
        """
        signals = []
        
        try:
            # 스크리닝 결과가 없으면 빈 리스트 반환
            if not candidate_results:
                self.logger.debug("📊 14:55 장중 스캔 결과 없음")
                return signals
            
            # 대기 중인 주문이 있는 종목들 추출
            pending_buy_stocks = set()
            if pending_orders:
                for order in pending_orders.values():
                    if hasattr(order, 'signal_type') and hasattr(order, 'stock_code'):
                        if order.signal_type == SignalType.BUY:
                            pending_buy_stocks.add(order.stock_code)
            
            self.logger.info(f"🔍 14:55 장중 스캔 결과: {len(candidate_results)}개 종목")
            
            # 상위 5개 고신뢰도 종목에 대해 즉시 매수 신호 생성
            processed_count = 0
            for candidate in candidate_results:
                # 최대 5개까지만 처리 (리스크 관리)
                if processed_count >= 5:
                    break
                
                # 이미 보유한 종목은 제외
                if candidate.stock_code in positions:
                    continue
                
                # 이미 매수 주문이 대기 중인 종목은 제외
                if candidate.stock_code in pending_buy_stocks:
                    self.logger.debug(f"⏸️ 매수 주문 대기 중인 종목 제외: {candidate.stock_name}")
                    continue
                
                # 🔥 14:55 즉시 매수는 최고 신뢰도만 선별 (패턴별 차별화)
                intraday_min_confidence = {
                    PatternType.MORNING_STAR: 90.0,        # 샛별: 90% 이상 (장중에는 최고 품질만)
                    PatternType.THREE_WHITE_SOLDIERS: 88.0, # 세 백병: 88% 이상
                    PatternType.ABANDONED_BABY: 88.0,      # 버려진 아기: 88% 이상
                    PatternType.BULLISH_ENGULFING: 85.0,   # 상승장악형: 85% 이상
                    PatternType.HAMMER: 80.0               # 망치형: 80% 이상
                }
                
                min_intraday_confidence = intraday_min_confidence.get(candidate.pattern_type, 85.0)
                
                if candidate.confidence < min_intraday_confidence:
                    self.logger.debug(f"⏸️ 14:55 장중 신뢰도 부족: {candidate.stock_name} "
                                    f"(신뢰도: {candidate.confidence:.1f}% < 최소: {min_intraday_confidence}%)")
                    continue
                
                # 🔧 중요: 14:55 장중 스캔에서는 실시간 현재가 조회 및 매수가 조정
                try:
                    # OrderManager를 통한 API 매니저 접근
                    api_manager = None
                    if self.order_manager and hasattr(self.order_manager, 'api_manager'):
                        api_manager = self.order_manager.api_manager
                    
                    realtime_price = None
                    if api_manager:
                        try:
                            price_info = api_manager.get_current_price(candidate.stock_code)
                            if price_info:
                                realtime_price = price_info.current_price
                                self.logger.debug(f"📊 {candidate.stock_name}: 실시간 현재가 조회 성공 - "
                                                f"스캔가: {candidate.current_price:,.0f}원, "
                                                f"현재가: {realtime_price:,.0f}원")
                        except Exception as api_error:
                            self.logger.warning(f"⚠️ {candidate.stock_name}: 실시간 현재가 조회 실패 - {api_error}")
                    
                    # 🎯 즉시 매수를 위한 가격 결정 로직
                    if realtime_price and realtime_price > 0:
                        # 실시간 현재가 조회 성공 시
                        base_price = realtime_price
                        
                        # 가격 차이가 5% 이상이면 경고
                        price_diff_ratio = abs(realtime_price - candidate.current_price) / candidate.current_price
                        if price_diff_ratio > 0.05:
                            self.logger.warning(f"⚠️ {candidate.stock_name}: 가격 차이 큼 - "
                                              f"스캔가: {candidate.current_price:,.0f}원, "
                                              f"현재가: {realtime_price:,.0f}원 "
                                              f"({price_diff_ratio*100:.1f}% 차이)")
                    else:
                        # 실시간 현재가 조회 실패 시 스캔 시점 가격 사용
                        base_price = candidate.current_price
                        self.logger.warning(f"⚠️ {candidate.stock_name}: 실시간 현재가 조회 실패, 스캔가 사용")
                    
                    # 🚀 14:55 즉시 매수용 가격 조정 (현재가 대비 약간 높게)
                    buy_price_adjustment = 0.001  # 0.1% 상향 (기존보다 보수적)
                    target_buy_price = base_price * (1 + buy_price_adjustment)
                    
                    # 호가 단위로 반올림 (100원 미만은 1원, 100원 이상은 5원 단위)
                    if target_buy_price < 100:
                        buy_price = round(target_buy_price)
                    elif target_buy_price < 1000:
                        buy_price = round(target_buy_price / 5) * 5
                    elif target_buy_price < 5000:
                        buy_price = round(target_buy_price / 10) * 10
                    elif target_buy_price < 10000:
                        buy_price = round(target_buy_price / 50) * 50
                    else:
                        buy_price = round(target_buy_price / 100) * 100
                    
                    self.logger.info(f"🎯 {candidate.stock_name}: 14:55 즉시 매수가 결정 - "
                                   f"기준가: {base_price:,.0f}원 → 매수가: {buy_price:,.0f}원 "
                                   f"({((buy_price/base_price-1)*100):+.1f}%)")
                    
                except Exception as price_error:
                    self.logger.error(f"❌ {candidate.stock_name}: 매수가 결정 오류 - {price_error}")
                    # 오류 발생 시 원래 가격 사용
                    buy_price = candidate.current_price
                
                # 📈 모든 패턴 허용 (기존 제한 제거) - 신뢰도가 충분히 높으면 모든 패턴 고려
                # 기존: 망치형, 상승장악형만 허용 → 변경: 모든 패턴 허용 (신뢰도로 필터링)
                
                # 💰 매수 수량 계산 (계좌 전체 금액의 8~15% 범위, 더 보수적)
                if account_info:
                    total_value = account_info.total_value
                    
                    # 신뢰도에 따라 투자 비율 결정 (85% -> 8%, 100% -> 15%)
                    confidence_ratio = candidate.confidence / 100.0
                    position_ratio = 0.08 + (0.07 * ((confidence_ratio - 0.85) / 0.15))  # 85~100% 신뢰도를 0~1로 정규화
                    
                    # 투자 금액 계산
                    target_amount = total_value * position_ratio
                    
                    # 가용 자금 확인
                    available_amount = account_info.available_amount
                    investment_amount = min(target_amount, available_amount)
                    
                    # 🔧 수정된 매수가로 수량 계산
                    quantity = int(investment_amount / buy_price)
                    
                    if quantity > 0:
                        signal = TradingSignal(
                            stock_code=candidate.stock_code,
                            stock_name=candidate.stock_name,
                            signal_type=SignalType.BUY,
                            price=buy_price,  # 🔧 수정: 조정된 매수가 사용
                            quantity=quantity,
                            reason=f"14:55 장중 즉시 매수 - {candidate.pattern_type.value} "
                                   f"(신뢰도: {candidate.confidence:.1f}%, 투자비율: {position_ratio:.1%}, "
                                   f"기준가: {base_price:,.0f}원)",
                            confidence=candidate.confidence / 100.0,
                            timestamp=now_kst(),
                            stop_loss_price=candidate.stop_loss,
                            take_profit_price=candidate.target_price,
                            metadata={
                                'pattern_type': candidate.pattern_type,
                                'market_cap_type': candidate.market_cap_type.value,
                                'pattern_strength': candidate.pattern_strength,
                                'volume_ratio': candidate.volume_ratio,
                                'original_scan_price': candidate.current_price,  # 원래 스캔 가격 보존
                                'realtime_base_price': base_price,  # 실시간 기준 가격
                                'price_adjustment': buy_price_adjustment  # 가격 조정률
                            }
                        )
                        signals.append(signal)
                        processed_count += 1
                        
                        self.logger.info(f"🚀 14:55 즉시 매수 신호 생성: {candidate.stock_name} "
                                       f"(신뢰도: {candidate.confidence:.1f}%)")
            
            if signals:
                self.logger.info(f"✅ 14:55 장중 즉시 매수 신호 {len(signals)}개 생성 완료")
            else:
                self.logger.info("📊 14:55 장중 즉시 매수 조건 만족하는 종목 없음")
                
        except Exception as e:
            self.logger.error(f"❌ 14:55 장중 매수 신호 생성 오류: {e}")
        
        return signals
    
    def execute_trading_signals(self, 
                              signals: List[TradingSignal],
                              positions: Dict[str, Position],
                              account_info: Optional[AccountInfo]) -> None:
        """
        매매 신호 실행
        
        Args:
            signals: 실행할 매매 신호 목록
            positions: 현재 포지션
            account_info: 계좌 정보
        """
        try:
            self.logger.debug("📊 매매 신호 처리 중...")
            
            # 매매 신호 처리
            for signal in signals:
                if signal.signal_type == SignalType.BUY:
                    self._execute_buy_order(signal, positions, account_info)
                elif signal.signal_type == SignalType.SELL:
                    self._execute_sell_order(signal, positions)
                    
        except Exception as e:
            self.logger.error(f"❌ 매매 신호 처리 오류: {e}")
    
    def _execute_buy_order(self, 
                          signal: TradingSignal,
                          positions: Dict[str, Position],
                          account_info: Optional[AccountInfo]) -> None:
        """매수 주문 실행"""
        try:
            if not self.order_manager:
                self.logger.error("❌ 주문 매니저 없음")
                return
            
            order_result = self.order_manager.execute_buy_order(signal, positions, account_info)
            
            if order_result and order_result.success:
                # 거래 기록 추가 (주문 성공 시)
                self._add_trade_record("BUY", signal, order_result)
                
                # ✅ 개선: 주문 성공 시 즉시 포지션 업데이트하지 않음
                # 실제 체결은 OrderManager의 콜백을 통해 처리됨
                # held_stocks_update_callback -> DatabaseExecutor.handle_buy_trade
                
                self.logger.info(f"📋 매수 주문 접수: {signal.stock_name} {signal.quantity}주 @ {signal.price:,.0f}원")
                self.logger.info(f"🔄 체결 대기 중... (주문ID: {order_result.order_id})")
                
        except Exception as e:
            self.logger.error(f"❌ 매수 주문 실행 오류: {e}")
    
    def _execute_sell_order(self, 
                           signal: TradingSignal,
                           positions: Dict[str, Position]) -> None:
        """매도 주문 실행"""
        try:
            if not self.order_manager:
                self.logger.error("❌ 주문 매니저 없음")
                return
            
            order_result = self.order_manager.execute_sell_order(signal, positions)
            
            if order_result and order_result.success:
                # 거래 기록 추가 (주문 성공 시)
                self._add_trade_record("SELL", signal, order_result)
                
                # ✅ 개선: 주문 성공 시 즉시 포지션 업데이트하지 않음
                # 실제 체결은 OrderManager의 콜백을 통해 처리됨
                # held_stocks_update_callback -> DatabaseExecutor.handle_sell_trade
                
                self.logger.info(f"📋 매도 주문 접수: {signal.stock_name} {signal.quantity}주 @ {signal.price:,.0f}원")
                self.logger.info(f"🔄 체결 대기 중... (주문ID: {order_result.order_id})")
                
        except Exception as e:
            self.logger.error(f"❌ 매도 주문 실행 오류: {e}")
    
    def _add_trade_record(self, 
                         trade_type: str, 
                         signal: TradingSignal, 
                         order_result: OrderResult) -> None:
        """거래 기록 추가"""
        try:
            record = TradeRecord(
                timestamp=now_kst(),
                trade_type=trade_type,
                stock_code=signal.stock_code,
                stock_name=signal.stock_name,
                quantity=signal.quantity,
                price=signal.price,
                amount=signal.quantity * signal.price,
                reason=signal.reason,
                order_id=order_result.order_id,
                success=order_result.success,
                message=order_result.message
            )
            
            self.trade_history.append(record)
            
            # 최근 1000건만 유지
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]
                
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 추가 오류: {e}")
    
    def get_trade_history(self) -> List[TradeRecord]:
        """거래 기록 반환"""
        return self.trade_history.copy()
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """거래 통계 반환"""
        try:
            successful_trades = sum(1 for record in self.trade_history if record.success)
            total_trades = len(self.trade_history)
            
            return {
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'failed_trades': total_trades - successful_trades,
                'win_rate': (successful_trades / total_trades * 100) if total_trades > 0 else 0.0
            }
        except Exception as e:
            self.logger.error(f"❌ 거래 통계 계산 오류: {e}")
            return {
                'total_trades': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'win_rate': 0.0
            }
    
    def _check_pattern_based_exit(self, position: Position) -> Optional[TradingSignal]:
        """
        패턴별 차별화된 매도 조건 확인
        
        Args:
            position: 포지션 정보
            
        Returns:
            Optional[TradingSignal]: 매도 신호 (조건 만족 시)
        """
        try:
            from trading.technical_analyzer import TechnicalAnalyzer
            
            # 패턴 타입이 없으면 패턴별 로직 적용 불가
            if not position.pattern_type:
                return None
            
            # 패턴 설정 가져오기
            pattern_config = TechnicalAnalyzer.get_pattern_config(position.pattern_type)
            if not pattern_config:
                return None
            
            current_time = now_kst()
            holding_days = safe_datetime_subtract(current_time, position.entry_time).days
            
            # 1. 🕐 패턴별 최대 보유기간 확인
            should_exit_time, time_reason = TechnicalAnalyzer.should_exit_by_time(
                position.pattern_type, position.entry_time, current_time
            )
            if should_exit_time:
                return TradingSignal(
                    stock_code=position.stock_code,
                    stock_name=position.stock_name,
                    signal_type=SignalType.SELL,
                    price=position.current_price,
                    quantity=position.quantity,
                    reason=f"패턴별 시간 기반 매도 - {time_reason}",
                    confidence=1.0,
                    timestamp=current_time
                )
            
            # 2. 💰 패턴별 부분 익절 확인
            should_partial_exit, partial_ratio, partial_reason = TechnicalAnalyzer.should_partial_exit(
                position.pattern_type, position.entry_time, current_time, position.profit_loss_rate
            )
            if should_partial_exit and not position.partial_sold:
                partial_quantity = int(position.quantity * partial_ratio)
                if partial_quantity > 0:
                    return TradingSignal(
                        stock_code=position.stock_code,
                        stock_name=position.stock_name,
                        signal_type=SignalType.SELL,
                        price=position.current_price,
                        quantity=partial_quantity,
                        reason=f"패턴별 부분 익절 - {partial_reason} "
                               f"({partial_ratio:.0%} 매도, 수익률: {position.profit_loss_rate:.1f}%)",
                        confidence=0.8,
                        timestamp=current_time
                    )
            
            # 3. 📉 패턴별 모멘텀 기반 종료 확인 (기술적 지표 필요 시 추가 구현)
            # 현재는 간단한 연속 하락 체크로 대체
            if pattern_config.momentum_exit:
                # 연속 3일 손실이 발생하고 있으면 모멘텀 소실로 판단
                if (holding_days >= 3 and 
                    position.profit_loss_rate < -0.01):  # 1% 이상 손실
                    
                    return TradingSignal(
                        stock_code=position.stock_code,
                        stock_name=position.stock_name,
                        signal_type=SignalType.SELL,
                        price=position.current_price,
                        quantity=position.quantity,
                        reason=f"패턴별 모멘텀 소실 매도 - {holding_days}일 보유, "
                               f"손실률: {position.profit_loss_rate:.2f}%",
                        confidence=0.9,
                        timestamp=current_time
                    )
            
            # 4. 🛑 패턴별 차별화된 손절매 확인
            if (position.stop_loss_price and 
                position.current_price <= position.stop_loss_price):
                
                return TradingSignal(
                    stock_code=position.stock_code,
                    stock_name=position.stock_name,
                    signal_type=SignalType.SELL,
                    price=position.current_price,
                    quantity=position.quantity,
                    reason=f"패턴별 손절매 - {pattern_config.pattern_name} "
                           f"({pattern_config.stop_loss_method})",
                    confidence=1.0,
                    timestamp=current_time
                )
            
            # 5. 🎯 패턴별 차별화된 익절매 확인
            if (position.take_profit_price and 
                position.current_price >= position.take_profit_price):
                
                return TradingSignal(
                    stock_code=position.stock_code,
                    stock_name=position.stock_name,
                    signal_type=SignalType.SELL,
                    price=position.current_price,
                    quantity=position.quantity,
                    reason=f"패턴별 익절매 - {pattern_config.pattern_name} "
                           f"목표 달성 (목표가: {position.take_profit_price:,.0f}원)",
                    confidence=1.0,
                    timestamp=current_time
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 패턴별 매도 조건 확인 오류: {e}")
            return None 