"""
하트비트 매니저 클래스

5분마다 시스템 상태를 전송하는 하트비트 기능을 담당합니다.
"""
import queue
from datetime import datetime
from typing import Optional, Dict, Any
from utils.logger import setup_logger
from utils.korean_time import now_kst
from .enums import TradingStatus, MarketStatus


class HeartbeatManager:
    """하트비트 신호 관리 클래스"""
    
    def __init__(self, message_queue: queue.Queue):
        """
        하트비트 매니저 초기화
        
        Args:
            message_queue: 텔레그램 봇으로 메시지를 보내는 큐
        """
        self.logger = setup_logger(__name__)
        self.message_queue = message_queue
        
        # 하트비트 설정
        self.last_heartbeat_time: Optional[datetime] = None
        self.heartbeat_interval = 10 * 60  # 10분 (초 단위)
        
        self.logger.info("✅ HeartbeatManager 초기화 완료")
    
    def should_send_heartbeat(self) -> bool:
        """하트비트를 전송해야 하는지 확인"""
        try:
            current_time = now_kst()
            
            if self.last_heartbeat_time is None:
                return True
            
            time_diff = (current_time - self.last_heartbeat_time).total_seconds()
            return time_diff >= self.heartbeat_interval
            
        except Exception as e:
            self.logger.error(f"❌ 하트비트 전송 시간 확인 오류: {e}")
            return False
    
    def send_heartbeat(self, 
                      status: TradingStatus, 
                      market_status: MarketStatus, 
                      held_stocks_count: int, 
                      buy_targets_count: int, 
                      account_info: Optional[Any] = None) -> None:
        """
        하트비트 신호 전송 (5분마다 시스템 상태 알림)
        
        Args:
            status: 매매봇 상태
            market_status: 장 상태
            held_stocks_count: 보유 종목 수
            buy_targets_count: 매수 대상 종목 수
            account_info: 계좌 정보 (선택사항)
        """
        try:
            current_time = now_kst()
            
            # 하트비트 메시지에 포함할 기본 정보
            heartbeat_info = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': status.value,
                'market_status': market_status.value,
                'held_stocks_count': held_stocks_count,
                'buy_targets_count': buy_targets_count,
                'total_value': account_info.total_value if account_info else 0,
                'available_amount': account_info.available_amount if account_info else 0
            }
            
            # 상태별 이모지 매핑
            status_emoji = {
                'RUNNING': '🟢',
                'PAUSED': '🟡', 
                'STOPPED': '🔴',
                'ERROR': '❌'
            }.get(status.value, '⚪')
            
            market_emoji = {
                'OPEN': '📈',
                'PRE_MARKET': '🌅',
                'CLOSED': '🌙'
            }.get(market_status.value, '⚪')
            
            # 하트비트 메시지 생성
            message = (
                f"💓 하트비트 {current_time.strftime('%H:%M')}\n"
                f"{status_emoji} 봇상태: {status.value}\n"
                f"{market_emoji} 장상태: {market_status.value}\n"
                f"📊 보유종목: {held_stocks_count}개\n"
                f"🎯 매수대상: {buy_targets_count}개"
            )
            
            # 계좌 정보가 있으면 추가
            if account_info:
                message += f"\n💰 총평가: {account_info.total_value:,.0f}원"
                message += f"\n💵 가용금액: {account_info.available_amount:,.0f}원"
            
            # 하트비트 메시지 전송
            self.message_queue.put({
                'type': 'heartbeat',
                'message': message,
                'data': heartbeat_info,
                'timestamp': current_time
            })
            
            # 마지막 하트비트 시간 업데이트
            self.last_heartbeat_time = current_time
            self.logger.debug(f"💓 하트비트 전송: {current_time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"❌ 하트비트 전송 오류: {e}")
    
    def reset_heartbeat_timer(self) -> None:
        """하트비트 타이머 리셋 (새로운 날 시작시 등)"""
        try:
            self.last_heartbeat_time = None
            self.logger.debug("🔄 하트비트 타이머 리셋")
        except Exception as e:
            self.logger.error(f"❌ 하트비트 타이머 리셋 오류: {e}")
    
    def set_heartbeat_interval(self, interval_minutes: int) -> None:
        """
        하트비트 간격 설정
        
        Args:
            interval_minutes: 하트비트 간격 (분 단위)
        """
        try:
            if interval_minutes <= 0:
                self.logger.warning("⚠️ 하트비트 간격은 0보다 커야 합니다")
                return
            
            self.heartbeat_interval = interval_minutes * 60
            self.logger.info(f"⏰ 하트비트 간격 설정: {interval_minutes}분")
        except Exception as e:
            self.logger.error(f"❌ 하트비트 간격 설정 오류: {e}")
    
    def get_heartbeat_status(self) -> Dict[str, Any]:
        """
        하트비트 상태 정보 반환
        
        Returns:
            Dict[str, Any]: 하트비트 상태 정보
        """
        try:
            current_time = now_kst()
            
            status_info = {
                'last_heartbeat': self.last_heartbeat_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_heartbeat_time else None,
                'interval_minutes': self.heartbeat_interval // 60,
                'next_heartbeat_in_seconds': None,
                'is_enabled': True
            }
            
            # 다음 하트비트까지 남은 시간 계산
            if self.last_heartbeat_time:
                elapsed = (current_time - self.last_heartbeat_time).total_seconds()
                remaining = max(0, self.heartbeat_interval - elapsed)
                status_info['next_heartbeat_in_seconds'] = int(remaining)
            
            return status_info
            
        except Exception as e:
            self.logger.error(f"❌ 하트비트 상태 조회 오류: {e}")
            return {} 