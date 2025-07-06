"""
주식 자동매매 봇 클래스

main.py에서 별도 스레드로 실행되는 매매 봇입니다.
KIS API를 통해 실제 매매를 수행하고, 큐를 통해 텔레그램 봇과 통신합니다.
"""
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from api.kis_api_manager import KISAPIManager, AccountInfo, StockPrice, OrderResult
from api.kis_auth import KisAuth
from utils.logger import setup_logger
from utils.korean_time import now_kst
from config.settings import validate_settings
from .enums import TradingStatus, MarketStatus, SignalType
from .models import TradingConfig, Position, TradingSignal, TradeRecord, AccountSnapshot
from trading.order_manager import OrderManager
from trading.position_manager import PositionManager
from trading.signal_manager import TradingSignalManager
from trading.candidate_screener import CandidateScreener, PatternResult
from database.db_executor import DatabaseExecutor


class TradingBot:
    """주식 자동매매 봇 클래스"""
    
    def __init__(self, message_queue: queue.Queue, command_queue: queue.Queue):
        """
        매매 봇 초기화
        
        Args:
            message_queue: 텔레그램 봇으로 메시지를 보내는 큐
            command_queue: 텔레그램 봇으로부터 명령을 받는 큐
        """
        self.logger = setup_logger(__name__)
        self.message_queue = message_queue
        self.command_queue = command_queue
        
        # 상태 관리
        self.status = TradingStatus.STOPPED
        self.market_status = MarketStatus.CLOSED
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        
        # 매매 설정
        self.config = TradingConfig()
        
        # 테스트 모드 설정 적용
        from config.settings import get_settings
        settings = get_settings()
        if settings:
            self.config.test_mode = settings.get_system_bool('test_mode', False)
            if self.config.test_mode:
                self.logger.info("🧪 테스트 모드 활성화 - 시간 제한 해제됨")
        
        # API 매니저
        self.api_manager: Optional[KISAPIManager] = None
        
        # 데이터베이스 실행자
        self.db_executor: Optional[DatabaseExecutor] = None
        
        # 계좌 정보
        self.account_info: Optional[AccountInfo] = None
        
        # 보유 종목 관리 (기존 positions)
        self.held_stocks: Dict[str, Position] = {}
        
        # 매매 관리자들
        self.order_handler: Optional[OrderManager] = None
        self.stock_manager: Optional[PositionManager] = None
        self.signal_generator: Optional[TradingSignalManager] = None
        
        # 패턴 스캐너 (기존 candidate_screener)
        self.pattern_scanner: Optional[CandidateScreener] = None
        self.buy_targets: List[PatternResult] = []  # 기존 candidate_results
        self.last_scan_time: Optional[datetime] = None  # 기존 last_screening_time
        
        # 효율적인 업데이트 관리
        self.account_loaded_today: bool = False  # 기존 account_info_loaded_today
        self.screening_completed_today: bool = False  # 기존 screening_done_today
        self.intraday_scan_completed_today: bool = False  # 14:55 장중 스캔 완료 플래그
        
        # 매매 기록 (호환성 유지를 위해 유지)
        self.trade_history: List[TradeRecord] = []
        
        # 통계 정보
        self.stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_profit_loss': 0.0,
            'win_rate': 0.0,
            'start_time': None,
            'last_update': None
        }
        
        self.logger.info("✅ TradingBot 초기화 완료")
    
    def initialize(self) -> bool:
        """
        매매 봇 초기화
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            self.logger.info("🚀 매매 봇 초기화 시작...")
            
            # 1. 설정 검증
            if not validate_settings():
                self.logger.error("❌ 설정 검증 실패")
                return False
            
            # 2. 데이터베이스 실행자 초기화
            self.db_executor = DatabaseExecutor()
            if not self.db_executor.initialize():
                self.logger.error("❌ 데이터베이스 실행자 초기화 실패")
                return False
            
            # 3. API 매니저 초기화
            self.api_manager = KISAPIManager()
            if not self.api_manager.initialize():
                self.logger.error("❌ KIS API 매니저 초기화 실패")
                return False
            
            # 2-1. 매매 관리자들 초기화
            self.order_handler = OrderManager(self.api_manager, self.config, self.message_queue)
            self.stock_manager = PositionManager(self.api_manager, self.config, self.message_queue)
            self.signal_generator = TradingSignalManager(self.config, self.order_handler, self.stock_manager, self.message_queue)
            
            # 2-1-1. 주문 추적 시작
            self.order_handler.start_order_tracking()
            
            # 2-1-1. OrderManager에 계좌 정보 업데이트 콜백 설정
            self.order_handler.set_account_update_callback(self.update_account_info_after_trade)
            
            # 2-1-2. OrderManager에 보유 종목 업데이트 콜백 설정
            self.order_handler.set_held_stocks_update_callback(self.update_held_stocks_after_trade)
            
            # 2-2. 패턴 스캐너 초기화
            try:
                auth = KisAuth()
                if auth.initialize():  # 명시적으로 초기화 호출
                    self.pattern_scanner = CandidateScreener(auth)
                    self.logger.info("✅ 패턴 스캐너 초기화 완료")
                else:
                    self.logger.warning("⚠️ 패턴 스캐너 초기화 실패 - KIS 인증 실패")
            except Exception as e:
                self.logger.warning(f"⚠️ 패턴 스캐너 초기화 실패: {e}")
                self.logger.info("ℹ️ 패턴 스캐너 없이 매매 봇을 계속 실행합니다")
            
            # 3. 계좌 정보 로드
            if not self._load_account_info():
                self.logger.error("❌ 계좌 정보 로드 실패")
                return False
            
            # 4. 기존 보유 종목 로드 (API + 데이터베이스 복원)
            if not self._load_existing_stocks():
                self.logger.error("❌ 기존 보유 종목 로드 실패")
                return False
            
            # 4-1. 데이터베이스에서 기존 포지션 복원
            if self.db_executor:
                self.held_stocks = self.db_executor.restore_positions_from_db(
                    self.held_stocks, self.buy_targets, self.api_manager
                )
            
            # 5. 장 상태 확인
            self._update_market_status()
            
            self.logger.info("✅ 매매 봇 초기화 완료")
            self._send_message("✅ 매매 봇이 성공적으로 초기화되었습니다.")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매매 봇 초기화 실패: {e}")
            self._send_message(f"❌ 매매 봇 초기화 실패: {e}")
            return False
    
    def start(self) -> bool:
        """
        매매 봇 시작
        
        Returns:
            bool: 시작 성공 여부
        """
        if self.is_running:
            self.logger.warning("⚠️ 매매 봇이 이미 실행 중입니다")
            return False
        
        try:
            self.is_running = True
            self.status = TradingStatus.RUNNING
            self.stats['start_time'] = now_kst()
            
            # 별도 스레드에서 매매 루프 실행
            self.thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.thread.start()
            
            self.logger.info("🚀 매매 봇 시작")
            self._send_message("🚀 매매 봇이 시작되었습니다.")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매매 봇 시작 실패: {e}")
            self._send_message(f"❌ 매매 봇 시작 실패: {e}")
            self.is_running = False
            self.status = TradingStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """
        매매 봇 정지
        
        Returns:
            bool: 정지 성공 여부
        """
        if not self.is_running:
            self.logger.warning("⚠️ 매매 봇이 실행 중이 아닙니다")
            return False
        
        try:
            self.is_running = False
            self.status = TradingStatus.STOPPED
            
            # 주문 추적 중지
            if self.order_handler:
                self.order_handler.stop_order_tracking()
            
            # 스레드 종료 대기
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            # 데이터베이스 연결 정리
            if self.db_executor:
                self.db_executor.close()
            
            self.logger.info("🛑 매매 봇 정지")
            self._send_message("🛑 매매 봇이 정지되었습니다.")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 매매 봇 정지 실패: {e}")
            self._send_message(f"❌ 매매 봇 정지 실패: {e}")
            return False
    
    def pause(self) -> bool:
        """
        매매 봇 일시정지
        
        Returns:
            bool: 일시정지 성공 여부
        """
        if self.status != TradingStatus.RUNNING:
            self.logger.warning("⚠️ 실행 중인 매매 봇만 일시정지할 수 있습니다")
            return False
        
        self.status = TradingStatus.PAUSED
        self.logger.info("⏸️ 매매 봇 일시정지")
        self._send_message("⏸️ 매매 봇이 일시정지되었습니다.")
        return True
    
    def resume(self) -> bool:
        """
        매매 봇 재개
        
        Returns:
            bool: 재개 성공 여부
        """
        if self.status != TradingStatus.PAUSED:
            self.logger.warning("⚠️ 일시정지된 매매 봇만 재개할 수 있습니다")
            return False
        
        self.status = TradingStatus.RUNNING
        self.logger.info("▶️ 매매 봇 재개")
        self._send_message("▶️ 매매 봇이 재개되었습니다.")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        매매 봇 상태 정보 반환
        
        Returns:
            Dict[str, Any]: 상태 정보
        """
        return {
            'status': self.status.value,
            'market_status': self.market_status.value,
            'is_running': self.is_running,
            'held_stocks_count': len(self.held_stocks),
            'account_info': self.account_info.__dict__ if self.account_info else None,
            'stats': self.stats.copy(),
            'config': self.config.__dict__,
            'order_tracking': self.order_handler.get_order_tracking_status() if self.order_handler else None,
            'last_update': now_kst().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    
    def force_pattern_scan(self) -> bool:
        """
        강제로 패턴 스캔 실행
        
        Returns:
            bool: 실행 성공 여부
        """
        try:
            if not self.pattern_scanner:
                self.logger.error("❌ 패턴 스캐너가 초기화되지 않았습니다")
                return False
            
            self.logger.info("🔍 강제 패턴 스캔 시작...")
            self._send_message("🔍 수동 패턴 스캔을 시작합니다...")
            
            # 강제 실행
            targets = self.pattern_scanner.run_candidate_screening(
                message_callback=self._send_message,
                force=True
            )
            
            # 결과를 TradingBot에서도 저장 (호환성 유지)
            self.buy_targets = targets
            if targets:
                self.last_scan_time = self.pattern_scanner.last_screening_time
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 강제 패턴 스캔 실패: {e}")
            self._send_message(f"❌ 강제 패턴 스캔 실패: {e}")
            return False
    
    def _trading_loop(self) -> None:
        """매매 메인 루프"""
        self.logger.info("🔄 매매 루프 시작")
        
        while self.is_running:
            try:
                # 1. 명령 처리
                self._process_commands()
                
                # 2. 상태가 RUNNING이 아니면 대기
                if self.status != TradingStatus.RUNNING:
                    time.sleep(1)
                    continue
                
                # 3. 장 상태 업데이트
                self._update_market_status()
                
                # 4. 장 시작 전 준비 작업 (하루 1회)
                if not self.account_loaded_today and self._should_load_account_info():
                    self._update_account_info()
                    self.account_loaded_today = True
                    self.logger.info("📊 오늘의 계좌 정보 로드 완료")
                
                # 5. 매수 대상 종목 패턴 스캔 (장 시작 전 특정 시간)
                if not self.screening_completed_today and self._should_run_pattern_scan():
                    self._execute_pattern_scan()
                    self.screening_completed_today = True
                    self.logger.info("🔍 오늘의 패턴 스캔 완료")
                
                # 5-1. 14:55 장중 스캔 및 즉시 매수 (하루 1회)
                if not self.intraday_scan_completed_today and self._should_run_intraday_scan():
                    self._execute_intraday_scan()
                    self.intraday_scan_completed_today = True
                    self.logger.info("🚀 오늘의 14:55 장중 스캔 완료")
                
                # 6. 새로운 날이 시작되면 플래그 리셋
                self._reset_daily_flags_if_needed()
                
                # 7. 매매 시간 중 보유 종목 현재가 업데이트 (실시간 손익 계산용)
                if self._is_trading_time() and self.held_stocks:
                    self._update_held_stocks()
                
                # 8. 매매 신호 생성 및 처리 (리스크 관리 포함)
                if self.signal_generator:
                    # 매매 신호 생성 전 계좌 잔고 빠른 업데이트 (수수료/세금 반영)
                    if self._is_trading_time() and self.api_manager:
                        quick_account_info = self.api_manager.get_account_balance_quick()
                        if quick_account_info:
                            # 기존 계좌 정보의 잔고 정보만 업데이트 (보유 종목 정보는 유지)
                            if self.account_info:
                                self.account_info.account_balance = quick_account_info.account_balance
                                self.account_info.available_amount = quick_account_info.available_amount
                                self.account_info.stock_value = quick_account_info.stock_value
                                self.account_info.total_value = quick_account_info.total_value
                                self.logger.debug(f"💰 계좌 잔고 빠른 업데이트: 가용금액 {self.account_info.available_amount:,.0f}원")
                    
                    # 대기 중인 주문 정보 가져오기 (중복 신호 방지용)
                    pending_orders = None
                    if self.order_handler:
                        pending_orders = self.order_handler.get_pending_orders()
                    
                    signals = self.signal_generator.generate_trading_signals(
                        self.buy_targets, self.held_stocks, self.account_info, pending_orders
                    )
                    self.signal_generator.execute_trading_signals(signals, self.held_stocks, self.account_info)
                
                # 9. 통계 업데이트
                self._update_stats()
                
                # 10. 대기
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                self.logger.error(f"❌ 매매 루프 오류: {e}")
                self.status = TradingStatus.ERROR
                self._send_message(f"❌ 매매 루프 오류: {e}")
                time.sleep(60)  # 오류 발생 시 1분 대기
        
        self.logger.info("🔄 매매 루프 종료")
    
    def _process_commands(self) -> None:
        """명령 큐에서 명령 처리"""
        try:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                self._handle_command(command)
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"❌ 명령 처리 오류: {e}")
    
    def _handle_command(self, command: Dict[str, Any]) -> None:
        """개별 명령 처리"""
        cmd_type = command.get('type', '')
        
        if cmd_type == 'pause':
            self.pause()
        elif cmd_type == 'resume':
            self.resume()
        elif cmd_type == 'stop':
            self.stop()
        elif cmd_type == 'status':
            status = self.get_status()
            # 상태 정보를 텔레그램 봇으로 전송
            self._send_status_response(status)
        elif cmd_type == 'screening':
            self.force_pattern_scan()
        elif cmd_type == 'candidates':
            # 매수 대상 종목 정보를 텔레그램 봇으로 전송
            self._send_buy_targets_response()
        elif cmd_type == 'orders':
            # 주문 추적 상태 정보를 텔레그램 봇으로 전송
            self._send_order_tracking_response()
        else:
            self.logger.warning(f"⚠️ 알 수 없는 명령: {cmd_type}")
    
    def _load_account_info(self) -> bool:
        """계좌 정보 로드"""
        try:
            if not self.api_manager:
                self.logger.error("❌ API 매니저가 초기화되지 않았습니다")
                return False
                
            self.account_info = self.api_manager.get_account_balance()
            if self.account_info:
                self.logger.info(f"💰 계좌 정보 로드 완료: 총 {self.account_info.total_value:,.0f}원")
                return True
            else:
                self.logger.error("❌ 계좌 정보 로드 실패")
                return False
        except Exception as e:
            self.logger.error(f"❌ 계좌 정보 로드 오류: {e}")
            return False
    
    def _load_existing_stocks(self) -> bool:
        """기존 보유 종목 로드"""
        try:
            if not self.stock_manager or not self.account_info:
                self.logger.error("❌ 종목 관리자 또는 계좌 정보 없음")
                return False
            
            self.held_stocks = self.stock_manager.load_existing_positions(self.account_info)
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 기존 보유 종목 로드 오류: {e}")
            return False
    
    def _update_market_status(self) -> None:
        """장 상태 업데이트"""
        try:
            # 테스트 모드일 때는 항상 장중으로 설정
            if self.config.test_mode:
                self.market_status = MarketStatus.OPEN
                return
            
            current_time = now_kst()
            hour = current_time.hour
            minute = current_time.minute
            
            # 평일 여부 확인 (0=월요일, 6=일요일)
            weekday = current_time.weekday()
            if weekday >= 5:  # 토요일(5), 일요일(6)
                self.market_status = MarketStatus.CLOSED
                return
            
            # 장 시간 확인
            if hour < 9:
                self.market_status = MarketStatus.PRE_MARKET
            elif hour == 9 and minute < 30:
                self.market_status = MarketStatus.PRE_MARKET
            elif (hour == 9 and minute >= 30) or (hour > 9 and hour < 15) or (hour == 15 and minute <= 30):
                self.market_status = MarketStatus.OPEN
            else:
                self.market_status = MarketStatus.CLOSED
                
        except Exception as e:
            self.logger.error(f"❌ 장 상태 업데이트 오류: {e}")
            self.market_status = MarketStatus.CLOSED
    
    def _is_trading_time(self) -> bool:
        """매매 가능 시간 확인"""
        # 테스트 모드일 때는 항상 매매 가능 시간으로 설정
        if self.config.test_mode:
            return True
            
        if self.market_status != MarketStatus.OPEN:
            return False
        
        current_time = now_kst()
        start_time = datetime.strptime(self.config.trading_start_time, "%H:%M").time()
        end_time = datetime.strptime(self.config.trading_end_time, "%H:%M").time()
        
        return start_time <= current_time.time() <= end_time
    
    def _update_account_info(self) -> None:
        """계좌 정보 및 보유 종목 업데이트"""
        try:
            if not self.api_manager:
                return
                
            # 1. 계좌 정보 업데이트
            self.account_info = self.api_manager.get_account_balance()
            if not self.account_info:
                self.logger.error("❌ 계좌 정보 업데이트 실패")
                return
                
            self.logger.debug(f"💰 계좌 정보 업데이트: 총 {self.account_info.total_value:,.0f}원")
            
            # 2. 기존 보유 종목 로드 (API에서 최신 정보 가져오기)
            if self.stock_manager:
                updated_positions = self.stock_manager.load_existing_positions(self.account_info)
                
                # 3. 데이터베이스에서 전략 정보 복원 (손절가, 익절가, 매수 이유 등)
                if self.db_executor:
                    self.held_stocks = self.db_executor.restore_positions_from_db(
                        updated_positions, self.buy_targets, self.api_manager
                    )
                    self.logger.debug(f"📊 보유 종목 업데이트 완료: {len(self.held_stocks)}개")
                else:
                    self.held_stocks = updated_positions
                    
        except Exception as e:
            self.logger.error(f"❌ 계좌 정보 및 보유 종목 업데이트 오류: {e}")
    
    def _update_held_stocks(self) -> None:
        """보유 종목 현재가 업데이트 (실시간 업데이트용)"""
        try:
            if self.stock_manager:
                self.stock_manager.update_positions(self.held_stocks)
        except Exception as e:
            self.logger.error(f"❌ 보유 종목 현재가 업데이트 오류: {e}")
    
    def _execute_pattern_scan(self) -> None:
        """패턴 스캔 실행"""
        try:
            self.logger.debug("🔍 매수 대상 종목 패턴 스캔 실행 중...")
            
            if not self.pattern_scanner:
                self.logger.warning("⚠️ 패턴 스캐너가 초기화되지 않았습니다")
                return
            
            # 매수 대상 종목 패턴 스캔 (하루에 한 번)
            targets = self.pattern_scanner.run_candidate_screening(
                message_callback=self._send_message,
                force=False
            )
            
            # 결과를 TradingBot에서도 저장 (호환성 유지)
            self.buy_targets = targets
            if targets:
                self.last_scan_time = self.pattern_scanner.last_screening_time
                
                # 데이터베이스에 후보종목 저장
                if self.db_executor:
                    self.db_executor.save_candidate_stocks(targets)
                    
        except Exception as e:
            self.logger.error(f"❌ 패턴 스캔 오류: {e}")
    
    def _execute_intraday_scan(self) -> None:
        """14:55 장중 스캔 실행"""
        try:
            self.logger.info("🔍 14:55 장중 스캔 실행 중...")
            
            if not self.pattern_scanner:
                self.logger.warning("⚠️ 패턴 스캐너가 초기화되지 않았습니다")
                return
            
            # 14:55 장중 스캔 실행
            intraday_targets = self.pattern_scanner.run_candidate_screening(
                message_callback=self._send_message,
                force=True  # 강제 실행
            )
            
            if intraday_targets:
                self.logger.info(f"🚀 14:55 장중 스캔 결과: {len(intraday_targets)}개 종목")
                
                # 즉시 매수 신호 생성
                if self.signal_generator:
                    # 대기 중인 주문 정보 가져오기
                    pending_orders = None
                    if self.order_handler:
                        pending_orders = self.order_handler.get_pending_orders()
                    
                    # 14:55 즉시 매수 신호 생성
                    intraday_signals = self.signal_generator.generate_intraday_buy_signals(
                        intraday_targets, self.held_stocks, self.account_info, pending_orders
                    )
                    
                    # 즉시 매수 실행
                    if intraday_signals:
                        self.signal_generator.execute_trading_signals(
                            intraday_signals, self.held_stocks, self.account_info
                        )
                        self._send_message(f"🚀 14:55 장중 즉시 매수 신호 {len(intraday_signals)}개 실행")
                    else:
                        self.logger.info("📊 14:55 장중 즉시 매수 조건 만족하는 종목 없음")
                        
            else:
                self.logger.info("📊 14:55 장중 스캔 결과: 조건 만족하는 종목 없음")
                    
        except Exception as e:
            self.logger.error(f"❌ 14:55 장중 스캔 오류: {e}")
    

    
    def _update_stats(self) -> None:
        """통계 정보 업데이트"""
        try:
            self.stats['last_update'] = now_kst()
            
            # 신호 생성기에서 거래 통계 가져오기
            if self.signal_generator:
                signal_stats = self.signal_generator.get_trade_statistics()
                self.stats.update(signal_stats)
                
                # 호환성을 위해 거래 기록도 동기화
                self.trade_history = self.signal_generator.get_trade_history()
            
            # 총 손익 계산
            total_profit_loss = sum(stock.profit_loss for stock in self.held_stocks.values())
            self.stats['total_profit_loss'] = total_profit_loss
            
        except Exception as e:
            self.logger.error(f"❌ 통계 업데이트 오류: {e}")
    
    def _should_load_account_info(self) -> bool:
        """계좌 정보를 로드해야 하는지 확인"""
        try:
            # 테스트 모드일 때는 항상 로드 가능
            if self.config.test_mode:
                return True
                
            current_time = now_kst()
            
            # 장 시작 전 (오전 8시 이후)에만 로드
            if current_time.hour >= 8 and current_time.hour < 9:
                return True
            
            # 또는 장 시작 직후 (9시 30분 ~ 10시)에도 로드 허용
            if current_time.hour == 9 and current_time.minute >= 30:
                return True
            if current_time.hour == 10 and current_time.minute < 30:
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 정보 로드 시간 확인 오류: {e}")
            return False
    
    def _should_run_pattern_scan(self) -> bool:
        """패턴 스캔을 실행해야 하는지 확인"""
        try:
            # 테스트 모드일 때는 항상 스캔 가능
            if self.config.test_mode:
                return True
                
            current_time = now_kst()
            
            # 장 시작 전 오전 8시 ~ 9시 사이에만 실행
            if current_time.hour == 8:
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 패턴 스캔 실행 시간 확인 오류: {e}")
            return False
    
    def _should_run_intraday_scan(self) -> bool:
        """14:55 장중 스캔을 실행해야 하는지 확인"""
        try:
            # 테스트 모드일 때는 항상 스캔 가능
            if self.config.test_mode:
                return True
                
            current_time = now_kst()
            
            # 14:55~15:00 사이에 실행 (프로그램 과부화 대비)
            if current_time.hour == 14 and current_time.minute >= 55:
                return True
            elif current_time.hour == 15 and current_time.minute == 0:
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 14:55 장중 스캔 실행 시간 확인 오류: {e}")
            return False
    
    def _reset_daily_flags_if_needed(self) -> None:
        """새로운 날이 시작되면 일일 플래그 리셋"""
        try:
            current_time = now_kst()
            
            # 자정 이후 오전 6시 사이에 플래그 리셋
            if current_time.hour < 6:
                if self.account_loaded_today or self.screening_completed_today or self.intraday_scan_completed_today:
                    self.account_loaded_today = False
                    self.screening_completed_today = False
                    self.intraday_scan_completed_today = False
                    self.logger.info("🔄 일일 플래그 리셋 완료")
                    
        except Exception as e:
            self.logger.error(f"❌ 일일 플래그 리셋 오류: {e}")
    
    def update_account_info_after_trade(self, trade_amount: float, is_buy: bool) -> None:
        """매매 후 계좌 정보 업데이트 (API 호출 없이 로컬 변수만 업데이트)"""
        try:
            if not self.account_info:
                self.logger.warning("⚠️ 계좌 정보가 없어 업데이트할 수 없습니다")
                return
            
            if is_buy:
                # 매수: 매수가능금액 감소, 주식 가치 증가
                self.account_info.available_amount -= trade_amount
                self.account_info.stock_value += trade_amount
            else:
                # 매도: 매수가능금액 증가, 주식 가치 감소
                self.account_info.available_amount += trade_amount
                self.account_info.stock_value -= trade_amount
            
            # 총 평가액 재계산 (순자산 + 주식가치)
            self.account_info.total_value = self.account_info.account_balance + self.account_info.stock_value
            
            # 실제로는 수수료를 차감해야 하지만, 여기서는 단순화
            
            self.logger.debug(f"💰 계좌 정보 업데이트: 매수가능 {self.account_info.available_amount:,.0f}원, 주식 {self.account_info.stock_value:,.0f}원")
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 정보 업데이트 오류: {e}")
    
    def update_held_stocks_after_trade(self, stock_code: str, stock_name: str, quantity: int, price: float, is_buy: bool) -> None:
        """매매 후 보유 종목 업데이트 및 데이터베이스 저장"""
        try:
            if self.db_executor:
                if is_buy:
                    self.db_executor.handle_buy_trade(
                        stock_code, stock_name, quantity, price,
                        self.held_stocks, self.buy_targets, self.config
                    )
                else:
                    self.db_executor.handle_sell_trade(
                        stock_code, stock_name, quantity, price,
                        self.held_stocks
                    )
            else:
                # DatabaseExecutor가 없는 경우 기본 처리
                if is_buy:
                    self.logger.debug(f"📊 매수 체결: {stock_name} {quantity}주 @ {price:,.0f}원")
                else:
                    self.logger.debug(f"📊 매도 체결: {stock_name} {quantity}주 @ {price:,.0f}원")
            
        except Exception as e:
            self.logger.error(f"❌ 보유 종목 업데이트 오류: {e}")
    

    
    def _send_message(self, message: str) -> None:
        """텔레그램 봇으로 메시지 전송"""
        try:
            self.message_queue.put({
                'type': 'info',
                'message': message,
                'timestamp': now_kst()
            })
        except Exception as e:
            self.logger.error(f"❌ 메시지 전송 오류: {e}")
    
    def _send_status_response(self, status: Dict[str, Any]) -> None:
        """상태 정보 응답 전송"""
        try:
            self.message_queue.put({
                'type': 'status_response',
                'data': status,
                'timestamp': now_kst()
            })
        except Exception as e:
            self.logger.error(f"❌ 상태 응답 전송 오류: {e}")
    
    def _send_buy_targets_response(self) -> None:
        """매수 대상 종목 응답 전송"""
        try:
            targets_data = []
            if self.buy_targets:
                for target in self.buy_targets[:10]:
                    targets_data.append({
                        'stock_code': target.stock_code,
                        'stock_name': target.stock_name,
                        'pattern_type': target.pattern_type.value if hasattr(target.pattern_type, 'value') else str(target.pattern_type),
                        'confidence': target.confidence,
                        'current_price': target.current_price
                    })
            
            self.message_queue.put({
                'type': 'candidates_response',
                'data': targets_data,
                'timestamp': now_kst()
            })
        except Exception as e:
            self.logger.error(f"❌ 매수 대상 응답 전송 오류: {e}")
    
    def _send_order_tracking_response(self) -> None:
        """주문 추적 상태 정보를 텔레그램 봇으로 전송"""
        try:
            order_tracking = self.order_handler.get_order_tracking_status() if self.order_handler else None
            response = {
                'type': 'order_tracking_response',
                'data': order_tracking,
                'timestamp': now_kst().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.message_queue.put(response)
        except Exception as e:
            self.logger.error(f"❌ 주문 추적 상태 정보 전송 오류: {e}")