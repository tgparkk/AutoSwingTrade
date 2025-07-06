"""
주문 관리 클래스

매수/매도 주문 실행 및 관리를 담당합니다.
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import queue
import asyncio
import threading

from api.kis_api_manager import KISAPIManager, OrderResult
from core.models import TradingSignal, TradingConfig, Position, TradeRecord, PendingOrder
from core.enums import SignalType, OrderType, OrderStatus, MessageType
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
        
        # 보유 종목 업데이트 콜백 (매수/매도 체결 시 held_stocks 업데이트용)
        self.held_stocks_update_callback: Optional[Callable[[str, str, int, float, bool], None]] = None
        
        # 주문 추적 관리
        self.pending_orders: Dict[str, PendingOrder] = {}  # 대기 중인 주문들
        self.order_tracking_active = False
        self.tracking_thread: Optional[threading.Thread] = None
        
        # 주문 통계
        self.order_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'buy_orders': 0,
            'sell_orders': 0,
            'partial_fills': 0,
            'cancelled_orders': 0,
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
    
    def set_held_stocks_update_callback(self, callback: Callable[[str, str, int, float, bool], None]) -> None:
        """
        보유 종목 업데이트 콜백 설정
        
        Args:
            callback: 콜백 함수 (stock_code: str, stock_name: str, quantity: int, price: float, is_buy: bool)
        """
        self.held_stocks_update_callback = callback
        self.logger.info("✅ 보유 종목 업데이트 콜백 설정 완료")
    
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
            
            # 2. 주문 수량 확인 (TradingSignalManager에서 이미 계산됨)
            if signal.quantity <= 0:
                self.logger.warning(f"⚠️ 매수 수량 없음: {signal.stock_name}")
                return None
            
            # 3. 주문 실행
            order_result = self.api_manager.place_buy_order(
                stock_code=signal.stock_code,
                quantity=signal.quantity,
                price=int(signal.price)
            )
            
            # 4. 결과 처리
            self._process_buy_order_result(signal, order_result, signal.quantity)
            
            # 5. 성공한 주문을 대기 목록에 추가
            if order_result and order_result.success:
                self.add_pending_order(order_result, signal)
            
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
            
            # 2. 주문 수량 조정 (대기 중인 매도 주문 고려)
            position = positions[signal.stock_code]
            
            # 🔍 현재 대기 중인 매도 주문 수량 계산
            pending_sell_quantity = self._get_pending_sell_quantity(signal.stock_code)
            
            # 🔍 실제 매도 가능 수량 계산
            available_quantity = position.quantity - pending_sell_quantity
            
            if available_quantity <= 0:
                self.logger.warning(f"⚠️ 매도 가능 수량 없음: {signal.stock_name} "
                                   f"(보유: {position.quantity}주, 대기 중: {pending_sell_quantity}주)")
                return None
            
            # 🔍 최종 매도 수량 결정
            sell_quantity = min(signal.quantity, available_quantity)
            
            if sell_quantity != signal.quantity:
                self.logger.info(f"📊 매도 수량 조정: {signal.stock_name} "
                               f"{signal.quantity}주 → {sell_quantity}주 "
                               f"(보유: {position.quantity}주, 대기 중: {pending_sell_quantity}주)")
            
            # 3. 주문 실행
            order_result = self.api_manager.place_sell_order(
                stock_code=signal.stock_code,
                quantity=sell_quantity,
                price=int(signal.price)
            )
            
            # 4. 결과 처리
            self._process_sell_order_result(signal, order_result, sell_quantity, position)
            
            # 5. 성공한 주문을 대기 목록에 추가
            if order_result and order_result.success:
                # 🔍 실제 주문 수량으로 신호 업데이트
                signal.quantity = sell_quantity
                self.add_pending_order(order_result, signal)
            
            return order_result
            
        except Exception as e:
            self.logger.error(f"❌ 매도 주문 실행 오류: {e}")
            self._send_message(f"❌ 매도 주문 실행 오류: {e}")
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
    
    # ========== 주문 추적 및 관리 기능 ==========
    
    def start_order_tracking(self) -> None:
        """주문 추적 시작"""
        if self.order_tracking_active:
            self.logger.warning("⚠️ 주문 추적이 이미 실행 중입니다")
            return
        
        self.order_tracking_active = True
        self.tracking_thread = threading.Thread(target=self._order_tracking_loop, daemon=True)
        self.tracking_thread.start()
        self.logger.info("✅ 주문 추적 시작")
    
    def stop_order_tracking(self) -> None:
        """주문 추적 중지"""
        if not self.order_tracking_active:
            return
        
        self.order_tracking_active = False
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=5)
        self.logger.info("✅ 주문 추적 중지")
    
    def _order_tracking_loop(self) -> None:
        """주문 추적 루프"""
        self.logger.info("🔄 주문 추적 루프 시작")
        
        while self.order_tracking_active:
            try:
                self._check_pending_orders()
                self._cleanup_completed_orders()
                
                # 10초마다 체크
                for _ in range(10):
                    if not self.order_tracking_active:
                        break
                    threading.Event().wait(1)
                
            except Exception as e:
                self.logger.error(f"❌ 주문 추적 루프 오류: {e}")
                threading.Event().wait(30)  # 오류 발생 시 30초 대기
        
        self.logger.info("🔄 주문 추적 루프 종료")
    
    def _check_pending_orders(self) -> None:
        """대기 중인 주문들 체결 확인"""
        if not self.pending_orders:
            return
        
        current_time = now_kst()
        orders_to_process = list(self.pending_orders.values())
        
        for pending_order in orders_to_process:
            try:
                # 주문 만료 확인
                if pending_order.is_expired:
                    self._handle_expired_order(pending_order)
                    continue
                
                # 체결 상태 확인
                self._check_order_status(pending_order)
                
            except Exception as e:
                self.logger.error(f"❌ 주문 체크 오류 [{pending_order.order_id}]: {e}")
    
    def _check_order_status(self, pending_order: PendingOrder) -> None:
        """개별 주문 체결 상태 확인"""
        try:
            # KIS API로 주문 상태 조회
            order_status = self.api_manager.get_order_status(pending_order.order_id)
            
            if not order_status:
                self.logger.warning(f"⚠️ 주문 상태 조회 실패: {pending_order.order_id}")
                return
            
            # 체결 정보 추출 (공식 API 문서 기준)
            filled_qty = int(order_status.get('tot_ccld_qty', 0))  # 총체결수량
            remaining_qty = int(order_status.get('rmn_qty', 0))    # 잔여수량
            order_qty = int(order_status.get('ord_qty', 0))        # 주문수량
            cancelled = order_status.get('cncl_yn', 'N')           # 취소여부
            
            # 상태 업데이트
            pending_order.filled_quantity = filled_qty
            pending_order.remaining_quantity = remaining_qty
            pending_order.last_check_time = now_kst()
            
            # 주문 취소 확인
            if cancelled == 'Y':
                pending_order.order_status = OrderStatus.CANCELLED
                pending_order.cancel_reason = "주문 취소"
                self.logger.info(f"❌ 주문 취소 확인: {pending_order.order_id}")
                return
            
            # 완전 체결 확인 (총체결수량 == 주문수량)
            if filled_qty > 0 and filled_qty == order_qty:
                self._handle_filled_order(pending_order)
            # 부분 체결 확인 (총체결수량 > 0 && 총체결수량 < 주문수량)
            elif filled_qty > 0 and filled_qty < order_qty:
                self._handle_partial_fill(pending_order)
            
        except Exception as e:
            self.logger.error(f"❌ 주문 상태 확인 오류 [{pending_order.order_id}]: {e}")
    
    def _handle_filled_order(self, pending_order: PendingOrder) -> None:
        """완전 체결된 주문 처리"""
        try:
            pending_order.order_status = OrderStatus.FILLED
            
            # 통계 업데이트
            self.order_stats['successful_orders'] += 1
            
            # 알림 전송
            message = (f"✅ {pending_order.stock_name} "
                      f"{'매수' if pending_order.signal_type == SignalType.BUY else '매도'} "
                      f"체결완료: {pending_order.quantity}주 @ {pending_order.price:,}원")
            
            self._send_message(message)
            
            # ✅ 완전 체결 시: 부분 체결로 이미 처리되지 않은 잔여 수량만 처리
            previous_filled_qty = getattr(pending_order, 'previous_filled_quantity', 0)
            remaining_filled_qty = pending_order.filled_quantity - previous_filled_qty
            
            if remaining_filled_qty > 0:
                # 계좌 정보 업데이트 콜백 호출 (잔여 체결량만)
                if self.account_update_callback:
                    trade_amount = remaining_filled_qty * pending_order.price
                    is_buy = pending_order.signal_type == SignalType.BUY
                    self.account_update_callback(trade_amount, is_buy)
                
                # 보유 종목 업데이트 콜백 호출 (잔여 체결량만)
                if self.held_stocks_update_callback:
                    is_buy = pending_order.signal_type == SignalType.BUY
                    self.held_stocks_update_callback(
                        pending_order.stock_code,
                        pending_order.stock_name,
                        remaining_filled_qty,  # ✅ 잔여 체결량만 전달
                        pending_order.price,
                        is_buy
                    )
            
            self.logger.info(f"✅ 주문 체결 완료: {pending_order.order_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 체결 주문 처리 오류: {e}")
    
    def _handle_partial_fill(self, pending_order: PendingOrder) -> None:
        """부분 체결 주문 처리"""
        try:
            # 기존 부분 체결량 저장 (새로운 체결량 계산용)
            previous_filled_qty = getattr(pending_order, 'previous_filled_quantity', 0)
            new_filled_qty = pending_order.filled_quantity - previous_filled_qty
            
            if new_filled_qty > 0:  # ✅ 새로운 체결량이 있을 때만 처리
                if pending_order.order_status != OrderStatus.PARTIAL_FILLED:
                    pending_order.order_status = OrderStatus.PARTIAL_FILLED
                    
                    # 통계 업데이트
                    self.order_stats['partial_fills'] += 1
                    
                    self.logger.info(f"🔄 부분 체결: {pending_order.order_id} "
                                   f"({pending_order.filled_quantity}/{pending_order.quantity})")
                
                # ✅ 새로운 체결량에 대해서만 계좌 정보 업데이트
                if self.account_update_callback:
                    new_filled_amount = new_filled_qty * pending_order.price
                    is_buy = pending_order.signal_type == SignalType.BUY
                    self.account_update_callback(new_filled_amount, is_buy)
                
                # ✅ 새로운 체결량에 대해서만 보유 종목 업데이트
                if self.held_stocks_update_callback:
                    is_buy = pending_order.signal_type == SignalType.BUY
                    self.held_stocks_update_callback(
                        pending_order.stock_code,
                        pending_order.stock_name,
                        new_filled_qty,  # ✅ 새로운 체결량만 전달
                        pending_order.price,
                        is_buy
                    )
            
            # 다음 체크를 위해 현재 체결량 저장
            pending_order.previous_filled_quantity = pending_order.filled_quantity
            
        except Exception as e:
            self.logger.error(f"❌ 부분 체결 처리 오류: {e}")
    
    def _handle_expired_order(self, pending_order: PendingOrder) -> None:
        """만료된 주문 처리 (취소)"""
        try:
            self.logger.warning(f"⏰ 주문 만료: {pending_order.order_id} "
                              f"({pending_order.timeout_minutes}분 경과)")
            
            # 주문 취소 시도
            cancel_result = self._cancel_order(pending_order)
            
            if cancel_result:
                pending_order.order_status = OrderStatus.CANCELLED
                pending_order.cancel_reason = "주문 만료"
                
                # 통계 업데이트
                self.order_stats['cancelled_orders'] += 1
                
                # 알림 전송
                message = (f"❌ {pending_order.stock_name} "
                          f"{'매수' if pending_order.signal_type == SignalType.BUY else '매도'} "
                          f"주문 취소: {pending_order.timeout_minutes}분 미체결")
                
                self._send_message(message)
                
                self.logger.info(f"❌ 만료 주문 취소 완료: {pending_order.order_id}")
            else:
                self.logger.error(f"❌ 만료 주문 취소 실패: {pending_order.order_id}")
                
        except Exception as e:
            self.logger.error(f"❌ 만료 주문 처리 오류: {e}")
    
    def _cancel_order(self, pending_order: PendingOrder) -> bool:
        """주문 취소 실행"""
        try:
            # KIS API로 주문 취소
            result = self.api_manager.cancel_order(
                order_id=pending_order.order_id,
                stock_code=pending_order.stock_code,
                order_type=pending_order.order_data.get('ord_dvsn', '00')
            )
            
            if result and result.success:
                return True
            else:
                error_msg = result.message if result else "주문 취소 실패"
                self.logger.error(f"❌ 주문 취소 실패: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 주문 취소 오류: {e}")
            return False
    
    def _cleanup_completed_orders(self) -> None:
        """완료된 주문들 정리"""
        try:
            completed_orders = []
            
            for order_id, pending_order in self.pending_orders.items():
                if pending_order.order_status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                    # 완료된 주문은 1분 후 정리
                    if (now_kst() - pending_order.last_check_time).total_seconds() > 60:
                        completed_orders.append(order_id)
            
            # 완료된 주문들 제거
            for order_id in completed_orders:
                del self.pending_orders[order_id]
                
            if completed_orders:
                self.logger.debug(f"🧹 완료된 주문 정리: {len(completed_orders)}건")
                
        except Exception as e:
            self.logger.error(f"❌ 주문 정리 오류: {e}")
    
    def add_pending_order(self, order_result: OrderResult, signal: TradingSignal) -> None:
        """대기 중인 주문 추가"""
        try:
            if not order_result or not order_result.order_id:
                self.logger.warning("⚠️ 유효하지 않은 주문 결과")
                return
            
            pending_order = PendingOrder(
                order_id=order_result.order_id,
                stock_code=signal.stock_code,
                stock_name=signal.stock_name,
                signal_type=signal.signal_type,
                order_type=signal.order_type,
                order_status=OrderStatus.PENDING,
                quantity=signal.quantity,
                price=signal.price,
                filled_quantity=0,
                remaining_quantity=signal.quantity,
                order_time=now_kst(),
                last_check_time=now_kst(),
                original_signal=signal,
                krx_fwdg_ord_orgno=getattr(order_result, 'krx_fwdg_ord_orgno', ''),
                order_data=getattr(order_result, 'order_data', {})
            )
            
            self.pending_orders[order_result.order_id] = pending_order
            self.logger.info(f"📋 대기 주문 추가: {order_result.order_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 대기 주문 추가 오류: {e}")
    
    def get_pending_orders(self) -> Dict[str, PendingOrder]:
        """대기 중인 주문 목록 반환"""
        return self.pending_orders.copy()
    
    def get_order_tracking_status(self) -> Dict[str, Any]:
        """주문 추적 상태 반환"""
        return {
            'active': self.order_tracking_active,
            'pending_count': len(self.pending_orders),
            'pending_orders': [
                {
                    'order_id': order.order_id,
                    'stock_name': order.stock_name,
                    'signal_type': order.signal_type.value,
                    'status': order.order_status.value,
                    'quantity': order.quantity,
                    'filled_quantity': order.filled_quantity,
                    'remaining_quantity': order.remaining_quantity,
                    'order_time': order.order_time.strftime('%H:%M:%S'),
                    'elapsed_minutes': (now_kst() - order.order_time).total_seconds() / 60
                }
                for order in self.pending_orders.values()
            ]
        }
    
    def _get_pending_sell_quantity(self, stock_code: str) -> int:
        """특정 종목의 대기 중인 매도 주문 수량 계산"""
        try:
            pending_quantity = 0
            
            for pending_order in self.pending_orders.values():
                if (pending_order.stock_code == stock_code and 
                    pending_order.signal_type == SignalType.SELL and
                    pending_order.order_status in [OrderStatus.PENDING, OrderStatus.PARTIAL_FILLED]):
                    
                    # 🔍 아직 체결되지 않은 수량만 계산
                    remaining_quantity = pending_order.remaining_quantity
                    pending_quantity += remaining_quantity
            
            return pending_quantity
            
        except Exception as e:
            self.logger.error(f"❌ 대기 중인 매도 수량 계산 오류: {e}")
            return 0 