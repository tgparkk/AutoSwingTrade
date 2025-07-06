"""
주문 관리 클래스

매수/매도 주문 실행 및 관리를 담당합니다.
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import queue

from api.kis_api_manager import KISAPIManager, OrderResult
from core.models import TradingSignal, TradingConfig, Position, TradeRecord
from core.enums import SignalType, OrderType
from utils.logger import setup_logger
from utils.korean_time import now_kst


class OrderManager:
    """주문 관리 클래스"""
    
    def __init__(self, api_manager: KISAPIManager, config: TradingConfig, message_queue: queue.Queue):
        """
        주문 관리자 초기화
        
        Args:
            api_manager: KIS API 매니저
            config: 매매 설정
            message_queue: 메시지 큐
        """
        self.logger = setup_logger(__name__)
        self.api_manager = api_manager
        self.config = config
        self.message_queue = message_queue
        
        # 계좌 정보 업데이트 콜백
        self.account_update_callback: Optional[Callable[[float, bool], None]] = None
        
        # 주문 통계
        self.order_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'buy_orders': 0,
            'sell_orders': 0,
            'last_order_time': None
        }
        
        self.logger.info("✅ OrderManager 초기화 완료")
    
    def set_account_update_callback(self, callback: Callable[[float, bool], None]) -> None:
        """
        계좌 정보 업데이트 콜백 설정
        
        Args:
            callback: 콜백 함수 (trade_amount: float, is_buy: bool)
        """
        self.account_update_callback = callback
        self.logger.info("✅ 계좌 정보 업데이트 콜백 설정 완료")
    
    def execute_buy_order(self, signal: TradingSignal, positions: Dict[str, Position], 
                         account_info: Any) -> Optional[OrderResult]:
        """
        매수 주문 실행
        
        Args:
            signal: 매수 신호
            positions: 현재 포지션
            account_info: 계좌 정보
            
        Returns:
            OrderResult: 주문 결과
        """
        try:
            # 1. 사전 검증
            if not self._validate_buy_order(signal, positions, account_info):
                return None
            
            # 2. 주문 수량 조정
            adjusted_quantity = self._adjust_buy_quantity(signal, account_info)
            if adjusted_quantity <= 0:
                self.logger.warning(f"⚠️ 매수 가능 수량 없음: {signal.stock_name}")
                return None
            
            # 3. 주문 실행
            order_result = self.api_manager.place_buy_order(
                stock_code=signal.stock_code,
                quantity=adjusted_quantity,
                price=int(signal.price)
            )
            
            # 4. 결과 처리
            self._process_buy_order_result(signal, order_result, adjusted_quantity)
            
            return order_result
            
        except Exception as e:
            self.logger.error(f"❌ 매수 주문 실행 오류: {e}")
            self._send_message(f"❌ 매수 주문 실행 오류: {e}")
            return None
    
    def execute_sell_order(self, signal: TradingSignal, positions: Dict[str, Position]) -> Optional[OrderResult]:
        """
        매도 주문 실행
        
        Args:
            signal: 매도 신호
            positions: 현재 포지션
            
        Returns:
            OrderResult: 주문 결과
        """
        try:
            # 1. 사전 검증
            if not self._validate_sell_order(signal, positions):
                return None
            
            # 2. 주문 수량 조정
            position = positions[signal.stock_code]
            sell_quantity = min(signal.quantity, position.quantity)
            
            # 3. 주문 실행
            order_result = self.api_manager.place_sell_order(
                stock_code=signal.stock_code,
                quantity=sell_quantity,
                price=int(signal.price)
            )
            
            # 4. 결과 처리
            self._process_sell_order_result(signal, order_result, sell_quantity, position)
            
            return order_result
            
        except Exception as e:
            self.logger.error(f"❌ 매도 주문 실행 오류: {e}")
            self._send_message(f"❌ 매도 주문 실행 오류: {e}")
            return None
    
    def execute_stop_loss_order(self, position: Position) -> Optional[OrderResult]:
        """
        손절 주문 실행
        
        Args:
            position: 포지션 정보
            
        Returns:
            OrderResult: 주문 결과
        """
        try:
            signal = TradingSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SignalType.SELL,
                price=position.current_price,
                quantity=position.quantity,
                reason="손절",
                confidence=1.0,
                timestamp=now_kst(),
                order_type=OrderType.STOP_LOSS
            )
            
            return self.execute_sell_order(signal, {position.stock_code: position})
            
        except Exception as e:
            self.logger.error(f"❌ 손절 주문 실행 오류: {e}")
            return None
    
    def execute_take_profit_order(self, position: Position) -> Optional[OrderResult]:
        """
        익절 주문 실행
        
        Args:
            position: 포지션 정보
            
        Returns:
            OrderResult: 주문 결과
        """
        try:
            signal = TradingSignal(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                signal_type=SignalType.SELL,
                price=position.current_price,
                quantity=position.quantity,
                reason="익절",
                confidence=1.0,
                timestamp=now_kst(),
                order_type=OrderType.TAKE_PROFIT
            )
            
            return self.execute_sell_order(signal, {position.stock_code: position})
            
        except Exception as e:
            self.logger.error(f"❌ 익절 주문 실행 오류: {e}")
            return None
    
    def _validate_buy_order(self, signal: TradingSignal, positions: Dict[str, Position], 
                           account_info: Any) -> bool:
        """매수 주문 검증"""
        try:
            # 계좌 정보 확인
            if not account_info:
                self.logger.warning("⚠️ 계좌 정보 없음")
                return False
            
            # 매수 가능 금액 확인 (최소 투자 금액)
            min_investment = account_info.total_value * self.config.min_position_ratio
            if account_info.available_amount < min_investment:
                self.logger.warning(f"⚠️ 매수 가능 금액 부족: {account_info.available_amount:,.0f}원 "
                                   f"(최소 필요: {min_investment:,.0f}원)")
                return False
            
            # 포지션 수 확인
            if len(positions) >= self.config.max_position_count:
                self.logger.warning(f"⚠️ 최대 포지션 수 초과: {len(positions)}/{self.config.max_position_count}")
                return False
            
            # 중복 포지션 확인
            if signal.stock_code in positions:
                self.logger.warning(f"⚠️ 이미 보유 중인 종목: {signal.stock_name}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매수 주문 검증 오류: {e}")
            return False
    
    def _validate_sell_order(self, signal: TradingSignal, positions: Dict[str, Position]) -> bool:
        """매도 주문 검증"""
        try:
            # 보유 포지션 확인
            if signal.stock_code not in positions:
                self.logger.warning(f"⚠️ 보유하지 않은 종목: {signal.stock_name}")
                return False
            
            position = positions[signal.stock_code]
            
            # 보유 수량 확인
            if position.quantity <= 0:
                self.logger.warning(f"⚠️ 보유 수량 없음: {signal.stock_name}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매도 주문 검증 오류: {e}")
            return False
    
    def _adjust_buy_quantity(self, signal: TradingSignal, account_info: Any) -> int:
        """매수 수량 조정"""
        try:
            # 가용 금액 기준 최대 수량 계산
            available_amount = account_info.available_amount
            max_quantity_by_amount = int(available_amount / signal.price)
            
            # 포트폴리오 비율 기준 최대 수량 계산
            max_investment = account_info.total_value * self.config.max_position_ratio
            max_quantity_by_ratio = int(max_investment / signal.price)
            
            # 최종 수량 결정
            adjusted_quantity = min(
                signal.quantity,
                max_quantity_by_amount,
                max_quantity_by_ratio
            )
            
            self.logger.debug(f"📊 수량 조정: {signal.quantity} → {adjusted_quantity}")
            return adjusted_quantity
            
        except Exception as e:
            self.logger.error(f"❌ 매수 수량 조정 오류: {e}")
            return 0
    
    def _process_buy_order_result(self, signal: TradingSignal, order_result: OrderResult, 
                                 quantity: int) -> None:
        """매수 주문 결과 처리"""
        try:
            self.order_stats['total_orders'] += 1
            self.order_stats['buy_orders'] += 1
            self.order_stats['last_order_time'] = now_kst()
            
            if order_result and order_result.success:
                self.order_stats['successful_orders'] += 1
                self.logger.info(f"✅ 매수 주문 성공: {signal.stock_name} {quantity}주 @ {signal.price:,.0f}원")
                
                # 상세 정보 로그
                self.logger.debug(f"📋 주문 상세: ID={order_result.order_id}, 금액={quantity * signal.price:,.0f}원")
                
                # 계좌 정보 업데이트 콜백 호출
                if self.account_update_callback:
                    trade_amount = quantity * signal.price
                    self.account_update_callback(trade_amount, True)  # True = 매수
                
            else:
                self.order_stats['failed_orders'] += 1
                error_msg = order_result.message if order_result else "주문 실패"
                self.logger.error(f"❌ 매수 주문 실패: {signal.stock_name} - {error_msg}")
                
        except Exception as e:
            self.logger.error(f"❌ 매수 주문 결과 처리 오류: {e}")
    
    def _process_sell_order_result(self, signal: TradingSignal, order_result: OrderResult, 
                                  quantity: int, position: Position) -> None:
        """매도 주문 결과 처리"""
        try:
            self.order_stats['total_orders'] += 1
            self.order_stats['sell_orders'] += 1
            self.order_stats['last_order_time'] = now_kst()
            
            if order_result and order_result.success:
                self.order_stats['successful_orders'] += 1
                
                # 손익 계산
                profit_loss = (signal.price - position.avg_price) * quantity
                profit_loss_rate = (signal.price - position.avg_price) / position.avg_price * 100
                
                self.logger.info(f"✅ 매도 주문 성공: {signal.stock_name} {quantity}주 @ {signal.price:,.0f}원")
                self.logger.info(f"💰 손익: {profit_loss:+,.0f}원 ({profit_loss_rate:+.2f}%)")
                
                # 상세 정보 로그
                self.logger.debug(f"📋 주문 상세: ID={order_result.order_id}, 사유={signal.reason}")
                
                # 계좌 정보 업데이트 콜백 호출
                if self.account_update_callback:
                    trade_amount = quantity * signal.price
                    self.account_update_callback(trade_amount, False)  # False = 매도
                
            else:
                self.order_stats['failed_orders'] += 1
                error_msg = order_result.message if order_result else "주문 실패"
                self.logger.error(f"❌ 매도 주문 실패: {signal.stock_name} - {error_msg}")
                
        except Exception as e:
            self.logger.error(f"❌ 매도 주문 결과 처리 오류: {e}")
    
    def get_order_stats(self) -> Dict[str, Any]:
        """주문 통계 반환"""
        try:
            stats = self.order_stats.copy()
            stats['success_rate'] = (
                (stats['successful_orders'] / stats['total_orders'] * 100) 
                if stats['total_orders'] > 0 else 0.0
            )
            return stats
        except Exception as e:
            self.logger.error(f"❌ 주문 통계 조회 오류: {e}")
            return {}
    
    def _send_message(self, message: str) -> None:
        """메시지 전송"""
        try:
            self.message_queue.put({
                'type': 'order',
                'message': message,
                'timestamp': now_kst()
            })
        except Exception as e:
            self.logger.error(f"❌ 메시지 전송 오류: {e}") 