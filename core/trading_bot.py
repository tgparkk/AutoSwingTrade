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
from .models import TradingConfig, Position, TradingSignal, TradeRecord
from trading.order_manager import OrderManager
from trading.position_manager import PositionManager
from trading.signal_manager import TradingSignalManager
from trading.candidate_screener import CandidateScreener, PatternResult


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
        
        # API 매니저
        self.api_manager: Optional[KISAPIManager] = None
        
        # 계좌 정보
        self.account_info: Optional[AccountInfo] = None
        
        # 포지션 관리
        self.positions: Dict[str, Position] = {}
        
        # 매매 관리자들
        self.order_manager: Optional[OrderManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.signal_manager: Optional[TradingSignalManager] = None
        
        # 캔들패턴 스크리너
        self.candidate_screener: Optional[CandidateScreener] = None
        self.candidate_results: List[PatternResult] = []
        self.last_screening_time: Optional[datetime] = None
        
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
            
            # 2. API 매니저 초기화
            self.api_manager = KISAPIManager()
            if not self.api_manager.initialize():
                self.logger.error("❌ KIS API 매니저 초기화 실패")
                return False
            
            # 2-1. 매매 관리자들 초기화
            self.order_manager = OrderManager(self.api_manager, self.config, self.message_queue)
            self.position_manager = PositionManager(self.api_manager, self.config, self.message_queue)
            self.signal_manager = TradingSignalManager(self.config, self.order_manager, self.position_manager, self.message_queue)
            
            # 2-2. 캔들패턴 스크리너 초기화
            try:
                auth = KisAuth()
                if auth.initialize():  # 명시적으로 초기화 호출
                    self.candidate_screener = CandidateScreener(auth)
                    self.logger.info("✅ 캔들패턴 스크리너 초기화 완료")
                else:
                    self.logger.warning("⚠️ 캔들패턴 스크리너 초기화 실패 - KIS 인증 실패")
            except Exception as e:
                self.logger.warning(f"⚠️ 캔들패턴 스크리너 초기화 실패: {e}")
                self.logger.info("ℹ️ 캔들패턴 스크리너 없이 매매 봇을 계속 실행합니다")
            
            # 3. 계좌 정보 로드
            if not self._load_account_info():
                self.logger.error("❌ 계좌 정보 로드 실패")
                return False
            
            # 4. 기존 포지션 로드
            if not self._load_existing_positions():
                self.logger.error("❌ 기존 포지션 로드 실패")
                return False
            
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
            
            # 스레드 종료 대기
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
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
            'positions_count': len(self.positions),
            'account_info': self.account_info.__dict__ if self.account_info else None,
            'stats': self.stats.copy(),
            'config': self.config.__dict__,
            'last_update': now_kst().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        현재 포지션 정보 반환
        
        Returns:
            List[Dict[str, Any]]: 포지션 목록
        """
        return [pos.__dict__ for pos in self.positions.values()]
    
    def get_candidate_results(self) -> List[Dict[str, Any]]:
        """
        매수후보 종목 결과 반환
        
        Returns:
            List[Dict[str, Any]]: 후보 종목 목록
        """
        return [
            {
                'stock_code': candidate.stock_code,
                'stock_name': candidate.stock_name,
                'pattern_type': candidate.pattern_type.value,
                'current_price': candidate.current_price,
                'target_price': candidate.target_price,
                'stop_loss': candidate.stop_loss,
                'confidence': candidate.confidence,
                'volume_ratio': candidate.volume_ratio,
                'technical_score': candidate.technical_score,
                'pattern_date': candidate.pattern_date
            }
            for candidate in self.candidate_results
        ]
    
    def force_screening(self) -> bool:
        """
        강제로 스크리닝 실행
        
        Returns:
            bool: 실행 성공 여부
        """
        try:
            if not self.candidate_screener:
                self.logger.error("❌ 캔들패턴 스크리너가 초기화되지 않았습니다")
                return False
            
            self.logger.info("🔍 강제 스크리닝 시작...")
            self._send_message("🔍 수동 스크리닝을 시작합니다...")
            
            # 강제 실행
            candidates = self.candidate_screener.run_candidate_screening(
                message_callback=self._send_message,
                force=True
            )
            
            # 결과를 TradingBot에서도 저장 (호환성 유지)
            self.candidate_results = candidates
            if candidates:
                self.last_screening_time = self.candidate_screener.last_screening_time
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 강제 스크리닝 실패: {e}")
            self._send_message(f"❌ 강제 스크리닝 실패: {e}")
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
                
                # 4. 장시간이 아니면 대기
                if not self._is_trading_time():
                    time.sleep(60)  # 장시간 외에는 1분마다 체크
                    continue
                
                # 5. 계좌 정보 업데이트
                self._update_account_info()
                
                # 6. 포지션 업데이트
                self._update_positions()
                
                # 7. 매수후보 종목 스크리닝
                self._execute_candidate_screening()
                
                # 8. 매매 신호 생성 및 처리
                if self.signal_manager:
                    signals = self.signal_manager.generate_trading_signals(
                        self.candidate_results, self.positions, self.account_info
                    )
                    self.signal_manager.execute_trading_signals(signals, self.positions, self.account_info)
                
                # 9. 리스크 관리
                self._manage_risk()
                
                # 10. 통계 업데이트
                self._update_stats()
                
                # 11. 대기
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
            self.force_screening()
        elif cmd_type == 'candidates':
            # 매수후보 종목 정보를 텔레그램 봇으로 전송
            self._send_candidates_response()
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
    
    def _load_existing_positions(self) -> bool:
        """기존 포지션 로드"""
        try:
            if not self.position_manager or not self.account_info:
                self.logger.error("❌ 포지션 매니저 또는 계좌 정보 없음")
                return False
            
            self.positions = self.position_manager.load_existing_positions(self.account_info)
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 기존 포지션 로드 오류: {e}")
            return False
    
    def _update_market_status(self) -> None:
        """장 상태 업데이트"""
        try:
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
        if self.market_status != MarketStatus.OPEN:
            return False
        
        current_time = now_kst()
        start_time = datetime.strptime(self.config.trading_start_time, "%H:%M").time()
        end_time = datetime.strptime(self.config.trading_end_time, "%H:%M").time()
        
        return start_time <= current_time.time() <= end_time
    
    def _update_account_info(self) -> None:
        """계좌 정보 업데이트"""
        try:
            if not self.api_manager:
                return
                
            self.account_info = self.api_manager.get_account_balance()
            if self.account_info:
                self.logger.debug(f"💰 계좌 정보 업데이트: 총 {self.account_info.total_value:,.0f}원")
        except Exception as e:
            self.logger.error(f"❌ 계좌 정보 업데이트 오류: {e}")
    
    def _update_positions(self) -> None:
        """포지션 정보 업데이트"""
        try:
            if self.position_manager:
                self.position_manager.update_positions(self.positions)
        except Exception as e:
            self.logger.error(f"❌ 포지션 업데이트 오류: {e}")
    
    def _execute_candidate_screening(self) -> None:
        """매수후보 종목 스크리닝 실행"""
        try:
            self.logger.debug("🔍 매수후보 종목 스크리닝 실행 중...")
            
            if not self.candidate_screener:
                self.logger.warning("⚠️ 캔들패턴 스크리너가 초기화되지 않았습니다")
                return
            
            # 매수후보 종목 스크리닝 (하루에 한 번)
            candidates = self.candidate_screener.run_candidate_screening(
                message_callback=self._send_message,
                force=False
            )
            
            # 결과를 TradingBot에서도 저장 (호환성 유지)
            self.candidate_results = candidates
            if candidates:
                self.last_screening_time = self.candidate_screener.last_screening_time
                    
        except Exception as e:
            self.logger.error(f"❌ 매수후보 종목 스크리닝 오류: {e}")
    
    def _manage_risk(self) -> None:
        """리스크 관리"""
        try:
            if not self.order_manager or not self.position_manager:
                return
            
            # 주의가 필요한 포지션 찾기
            attention_positions = self.position_manager.get_positions_requiring_attention(self.positions)
            
            for position in attention_positions:
                # 손절 조건 확인
                if position.profit_loss_rate <= self.config.stop_loss_ratio * 100:
                    self.logger.warning(f"⚠️ 손절 조건 충족: {position.stock_name} ({position.profit_loss_rate:.2f}%)")
                    order_result = self.order_manager.execute_stop_loss_order(position)
                    
                    if order_result and order_result.success:
                        # 포지션 제거
                        if position.stock_code in self.positions:
                            del self.positions[position.stock_code]
                
                # 익절 조건 확인
                elif position.profit_loss_rate >= self.config.take_profit_ratio * 100:
                    self.logger.info(f"✅ 익절 조건 충족: {position.stock_name} ({position.profit_loss_rate:.2f}%)")
                    order_result = self.order_manager.execute_take_profit_order(position)
                    
                    if order_result and order_result.success:
                        # 포지션 제거
                        if position.stock_code in self.positions:
                            del self.positions[position.stock_code]
                    
        except Exception as e:
            self.logger.error(f"❌ 리스크 관리 오류: {e}")
    
    def _update_stats(self) -> None:
        """통계 정보 업데이트"""
        try:
            self.stats['last_update'] = now_kst()
            
            # 신호 관리자에서 거래 통계 가져오기
            if self.signal_manager:
                signal_stats = self.signal_manager.get_trade_statistics()
                self.stats.update(signal_stats)
                
                # 호환성을 위해 거래 기록도 동기화
                self.trade_history = self.signal_manager.get_trade_history()
            
            # 총 손익 계산
            total_profit_loss = sum(pos.profit_loss for pos in self.positions.values())
            self.stats['total_profit_loss'] = total_profit_loss
            
        except Exception as e:
            self.logger.error(f"❌ 통계 업데이트 오류: {e}")
    
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
    
    def _send_candidates_response(self) -> None:
        """매수후보 종목 응답 전송"""
        try:
            candidates_data = []
            if self.candidate_results:
                for candidate in self.candidate_results[:10]:
                    candidates_data.append({
                        'stock_code': candidate.stock_code,
                        'stock_name': candidate.stock_name,
                        'pattern_type': candidate.pattern_type.value if hasattr(candidate.pattern_type, 'value') else str(candidate.pattern_type),
                        'confidence': candidate.confidence,
                        'current_price': candidate.current_price
                    })
            
            self.message_queue.put({
                'type': 'candidates_response',
                'data': candidates_data,
                'timestamp': now_kst()
            })
        except Exception as e:
            self.logger.error(f"❌ 매수후보 응답 전송 오류: {e}")