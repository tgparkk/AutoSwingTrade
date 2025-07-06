"""
데이터베이스 실행 클래스

TradingBot의 데이터베이스 관련 작업을 처리하는 클래스입니다.
포지션 관리, 거래 기록, 후보종목 저장 등의 DB 작업을 담당합니다.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.logger import setup_logger
from utils.korean_time import now_kst
from core.models import Position, TradeRecord, AccountSnapshot
from core.enums import PositionStatus, OrderType
from trading.candidate_screener import PatternResult
from .db_manager import DatabaseManager


class DatabaseExecutor:
    """데이터베이스 실행 클래스"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        """
        데이터베이스 실행자 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.logger = setup_logger(__name__)
        self.db_manager = DatabaseManager(db_path)
    
    def initialize(self) -> bool:
        """데이터베이스 초기화"""
        try:
            return self.db_manager.initialize_database()
        except Exception as e:
            self.logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
            return False
    
    def save_candidate_stocks(self, candidates: List[PatternResult]) -> bool:
        """
        후보종목을 데이터베이스에 저장
        
        Args:
            candidates: 후보종목 리스트
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            if not candidates:
                return True
                
            screening_date = now_kst().strftime('%Y-%m-%d')
            candidate_ids = self.db_manager.save_candidate_stocks(candidates, screening_date)
            
            if candidate_ids:
                self.logger.info(f"✅ 후보종목 {len(candidate_ids)}개 데이터베이스 저장 완료")
                return True
            else:
                self.logger.warning("⚠️ 후보종목 저장 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 후보종목 데이터베이스 저장 오류: {e}")
            return False
    
    def restore_positions_from_db(self, api_positions: Dict[str, Position], 
                                 buy_targets: List[PatternResult],
                                 api_manager: Any) -> Dict[str, Position]:
        """
        데이터베이스에서 기존 포지션 복원
        
        Args:
            api_positions: API에서 가져온 포지션 딕셔너리
            buy_targets: 현재 매수 대상 리스트
            api_manager: API 매니저 (현재가 조회용)
            
        Returns:
            Dict[str, Position]: 복원된 포지션 딕셔너리
        """
        try:
            # 데이터베이스에서 활성 포지션 조회
            db_positions = self.db_manager.load_active_positions()
            
            if not db_positions:
                self.logger.info("ℹ️ 복원할 포지션이 없습니다")
                return api_positions
            
            # 기존 held_stocks와 병합
            restored_positions = api_positions.copy()
            restored_count = 0
            
            for stock_code, db_position in db_positions.items():
                if stock_code in restored_positions:
                    # API에서 가져온 정보와 데이터베이스 정보 병합
                    api_position = restored_positions[stock_code]
                    
                    # 손절가, 익절가, 매수 이유 등의 전략 정보 복원
                    api_position.stop_loss_price = db_position.stop_loss_price
                    api_position.take_profit_price = db_position.take_profit_price
                    api_position.entry_reason = db_position.entry_reason
                    api_position.entry_time = db_position.entry_time
                    api_position.notes = db_position.notes
                    api_position.target_price = db_position.target_price
                    
                    self.logger.info(f"🔄 포지션 병합: {api_position.stock_name} - 전략 정보 복원 완료")
                    restored_count += 1
                else:
                    # API에는 없지만 데이터베이스에는 있는 경우 (부분 매도 등)
                    # 현재가 업데이트 필요
                    if api_manager:
                        try:
                            current_price_info = api_manager.get_current_price(stock_code)
                            if current_price_info:
                                db_position.current_price = current_price_info.current_price
                                # 손익 재계산
                                db_position.profit_loss = (current_price_info.current_price - db_position.avg_price) * db_position.quantity
                                db_position.profit_loss_rate = (current_price_info.current_price / db_position.avg_price - 1) * 100
                                db_position.last_update = now_kst()
                        except Exception as e:
                            self.logger.warning(f"⚠️ 현재가 업데이트 실패 {stock_code}: {e}")
                    
                    restored_positions[stock_code] = db_position
                    self.logger.info(f"➕ 포지션 복원: {db_position.stock_name} - 데이터베이스에서 복원")
                    restored_count += 1
            
            self.logger.info(f"✅ 포지션 복원 완료: {restored_count}개 종목")
            return restored_positions
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 복원 오류: {e}")
            return api_positions
    
    def set_strategy_info_for_new_position(self, position: Position, 
                                         buy_targets: List[PatternResult],
                                         config: Any) -> None:
        """
        새로운 포지션에 전략 정보 설정
        
        Args:
            position: 포지션 객체
            buy_targets: 매수 대상 리스트
            config: 매매 설정
        """
        try:
            # 후보종목에서 해당 종목 찾기
            target_candidate = None
            for candidate in buy_targets:
                if candidate.stock_code == position.stock_code:
                    target_candidate = candidate
                    break
            
            if target_candidate:
                # 후보종목 정보를 기반으로 전략 정보 설정
                position.target_price = target_candidate.target_price
                position.stop_loss_price = target_candidate.stop_loss
                position.entry_reason = f"패턴: {target_candidate.pattern_type.value}, 신뢰도: {target_candidate.confidence:.1f}%"
                
                self.logger.debug(f"🎯 전략 정보 설정: {position.stock_name} - 목표가: {position.target_price:,.0f}원, 손절가: {position.stop_loss_price:,.0f}원")
            else:
                # 기본 전략 정보 설정
                position.stop_loss_price = position.avg_price * (1 + config.stop_loss_ratio)
                position.take_profit_price = position.avg_price * (1 + config.take_profit_ratio)
                position.entry_reason = "일반 매수"
                
                self.logger.debug(f"🎯 기본 전략 정보 설정: {position.stock_name}")
                
        except Exception as e:
            self.logger.error(f"❌ 전략 정보 설정 오류: {e}")
    
    def handle_buy_trade(self, stock_code: str, stock_name: str, quantity: int, price: float,
                        held_stocks: Dict[str, Position], buy_targets: List[PatternResult],
                        config: Any) -> bool:
        """
        매수 체결 처리
        
        Args:
            stock_code: 종목코드
            stock_name: 종목명
            quantity: 수량
            price: 가격
            held_stocks: 보유 종목 딕셔너리
            buy_targets: 매수 대상 리스트
            config: 매매 설정
            
        Returns:
            bool: 처리 성공 여부
        """
        try:
            if stock_code in held_stocks:
                # 기존 보유 종목 평균가 계산
                position = held_stocks[stock_code]
                total_quantity = position.quantity + quantity
                total_amount = (position.avg_price * position.quantity) + (price * quantity)
                new_avg_price = total_amount / total_quantity
                
                position.quantity = total_quantity
                position.avg_price = new_avg_price
                position.last_update = now_kst()
                
                # 데이터베이스 업데이트
                self.db_manager.update_position(position)
                
                self.logger.debug(f"📊 보유 종목 추가: {stock_name} {quantity}주 @ {price:,.0f}원 (평균가: {new_avg_price:,.0f}원)")
            else:
                # 새로운 보유 종목 추가
                new_position = Position(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    quantity=quantity,
                    avg_price=price,
                    current_price=price,
                    profit_loss=0.0,
                    profit_loss_rate=0.0,
                    entry_time=now_kst(),
                    last_update=now_kst(),
                    status=PositionStatus.ACTIVE,
                    order_type=OrderType.LIMIT,
                    entry_reason="매수 체결"
                )
                
                # 전략 정보 설정
                self.set_strategy_info_for_new_position(new_position, buy_targets, config)
                
                held_stocks[stock_code] = new_position
                
                # 데이터베이스 저장
                self.db_manager.save_position(new_position)
                
                self.logger.debug(f"📊 신규 보유 종목 추가: {stock_name} {quantity}주 @ {price:,.0f}원")
            
            # 거래 기록 저장
            self.save_trade_record(stock_code, stock_name, quantity, price, True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매수 체결 처리 오류: {e}")
            return False
    
    def handle_sell_trade(self, stock_code: str, stock_name: str, quantity: int, price: float,
                         held_stocks: Dict[str, Position]) -> bool:
        """
        매도 체결 처리
        
        Args:
            stock_code: 종목코드
            stock_name: 종목명
            quantity: 수량
            price: 가격
            held_stocks: 보유 종목 딕셔너리
            
        Returns:
            bool: 처리 성공 여부
        """
        try:
            if stock_code in held_stocks:
                position = held_stocks[stock_code]
                position.quantity -= quantity
                position.last_update = now_kst()
                
                if position.quantity <= 0:
                    # 보유 종목 완전 매도
                    del held_stocks[stock_code]
                    
                    # 데이터베이스에서 삭제
                    self.db_manager.remove_position(stock_code)
                    
                    self.logger.debug(f"📊 보유 종목 완전 매도: {stock_name} {quantity}주 @ {price:,.0f}원")
                else:
                    # 데이터베이스 업데이트
                    self.db_manager.update_position(position)
                    
                    self.logger.debug(f"📊 보유 종목 부분 매도: {stock_name} {quantity}주 @ {price:,.0f}원 (잔여: {position.quantity}주)")
            else:
                self.logger.warning(f"⚠️ 매도하려는 종목이 보유 목록에 없습니다: {stock_name}")
            
            # 거래 기록 저장
            self.save_trade_record(stock_code, stock_name, quantity, price, False)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매도 체결 처리 오류: {e}")
            return False
    
    def save_trade_record(self, stock_code: str, stock_name: str, quantity: int, price: float, is_buy: bool) -> bool:
        """
        거래 기록을 데이터베이스에 저장
        
        Args:
            stock_code: 종목코드
            stock_name: 종목명
            quantity: 수량
            price: 가격
            is_buy: 매수 여부
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            trade_record = TradeRecord(
                timestamp=now_kst(),
                trade_type="BUY" if is_buy else "SELL",
                stock_code=stock_code,
                stock_name=stock_name,
                quantity=quantity,
                price=price,
                amount=quantity * price,
                reason="자동매매 체결",
                order_id=f"AUTO_{now_kst().strftime('%Y%m%d_%H%M%S')}_{stock_code}",
                success=True,
                message="체결 완료",
                execution_time=now_kst()
            )
            
            trade_id = self.db_manager.save_trade_record(trade_record)
            return trade_id is not None
            
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 저장 오류: {e}")
            return False
    
    def save_account_snapshot(self, account_info: Any) -> bool:
        """
        계좌 스냅샷 저장
        
        Args:
            account_info: 계좌 정보
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            if not account_info:
                return False
                
            snapshot = AccountSnapshot(
                timestamp=now_kst(),
                total_value=account_info.total_value,
                available_amount=account_info.available_amount,
                stock_value=account_info.stock_value,
                cash_balance=account_info.account_balance,
                profit_loss=0.0,  # 계산 필요
                profit_loss_rate=0.0,  # 계산 필요
                position_count=len(account_info.positions),
                daily_trades=0,  # 별도 계산 필요
                daily_profit_loss=0.0  # 별도 계산 필요
            )
            
            snapshot_id = self.db_manager.save_account_snapshot(snapshot)
            return snapshot_id is not None
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 스냅샷 저장 오류: {e}")
            return False
    
    def get_recent_candidates(self, days: int = 7) -> List[PatternResult]:
        """
        최근 후보종목 조회
        
        Args:
            days: 조회할 일수
            
        Returns:
            List[PatternResult]: 후보종목 리스트
        """
        try:
            return self.db_manager.get_recent_candidates(days)
        except Exception as e:
            self.logger.error(f"❌ 최근 후보종목 조회 오류: {e}")
            return []
    
    def get_trade_history(self, stock_code: Optional[str] = None, days: int = 30) -> List[TradeRecord]:
        """
        거래 기록 조회
        
        Args:
            stock_code: 종목코드 (선택사항)
            days: 조회할 일수
            
        Returns:
            List[TradeRecord]: 거래 기록 리스트
        """
        try:
            return self.db_manager.get_trade_history(stock_code, days)
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 조회 오류: {e}")
            return []
    
    def close(self) -> None:
        """데이터베이스 연결 종료"""
        try:
            self.db_manager.close()
        except Exception as e:
            self.logger.error(f"❌ 데이터베이스 연결 종료 오류: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 