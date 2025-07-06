"""
매매 신호 관리자 클래스

매매 신호 생성과 실행을 담당하는 클래스입니다.
"""
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from utils.logger import setup_logger
from utils.korean_time import now_kst
from core.enums import SignalType
from core.models import TradingConfig, Position, TradingSignal, TradeRecord
from trading.candidate_screener import PatternResult
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
                               account_info: Optional[AccountInfo]) -> List[TradingSignal]:
        """
        매매 신호 생성 (캔들패턴 기반)
        
        Args:
            candidate_results: 매수후보 종목 결과
            positions: 현재 포지션
            account_info: 계좌 정보
            
        Returns:
            List[TradingSignal]: 생성된 매매 신호 목록
        """
        signals = []
        
        try:
            # 스크리닝 결과가 없으면 빈 리스트 반환
            if not candidate_results:
                return signals
            
            # 상위 5개 후보 종목에 대해 매수 신호 생성
            for candidate in candidate_results[:5]:
                # 이미 보유한 종목은 제외
                if candidate.stock_code in positions:
                    continue
                
                # 신뢰도 70% 이상인 종목만 선택
                if candidate.confidence < 70.0:
                    continue
                
                # 매수 수량 계산 (계좌 전체 금액의 10~20% 범위)
                if account_info:
                    total_value = account_info.total_value
                    
                    # 신뢰도에 따라 투자 비율 결정 (70% -> 10%, 100% -> 20%)
                    confidence_ratio = candidate.confidence / 100.0
                    position_ratio = self.config.min_position_ratio + (
                        (self.config.max_position_ratio - self.config.min_position_ratio) * 
                        ((confidence_ratio - 0.7) / 0.3)  # 70~100% 신뢰도를 0~1로 정규화
                    )
                    
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
                            take_profit_price=candidate.target_price
                        )
                        signals.append(signal)
            
            # 기존 포지션에 대한 매도 신호 생성
            for position in positions.values():
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
                    elif position.profit_loss_rate >= 3.0:  # 3% 수익
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
                # 거래 기록 추가
                self._add_trade_record("BUY", signal, order_result)
                
                # 포지션 업데이트 (새로운 매수 포지션 추가)
                if self.position_manager:
                    self.position_manager.update_position_after_trade(
                        positions, signal.stock_code, "BUY", signal.quantity, signal.price,
                        stop_loss_price=signal.stop_loss_price,
                        take_profit_price=signal.take_profit_price
                    )
                
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
                # 포지션 업데이트
                if self.position_manager:
                    self.position_manager.update_position_after_trade(
                        positions, signal.stock_code, "SELL", signal.quantity, signal.price
                    )
                
                # 포지션 제거 (수량이 0이 된 경우)
                if signal.stock_code in positions and positions[signal.stock_code].quantity <= 0:
                    del positions[signal.stock_code]
                
                # 거래 기록 추가
                self._add_trade_record("SELL", signal, order_result)
                
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