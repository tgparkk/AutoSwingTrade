"""
주식 자동매매 시스템 메인 실행 파일

매매 봇과 텔레그램 봇을 별도 스레드로 실행하고,
큐를 통해 스레드 간 통신을 관리합니다.
"""
import sys
import time
import signal
import queue
import threading
from datetime import datetime
from typing import Optional

from core.trading_bot import TradingBot
from telegram_bot import TelegramBot
from utils.logger import setup_logger
from utils.korean_time import now_kst
from config.settings import validate_settings, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_settings


class AutoSwingTradeSystem:
    """자동매매 시스템 메인 클래스"""
    
    def __init__(self):
        """시스템 초기화"""
        self.logger = setup_logger(__name__)
        
        # 스레드 간 통신 큐
        self.message_queue = queue.Queue()  # 매매봇 -> 텔레그램봇
        self.command_queue = queue.Queue()  # 텔레그램봇 -> 매매봇
        
        # 봇 인스턴스
        self.trading_bot: Optional[TradingBot] = None
        self.telegram_bot: Optional[TelegramBot] = None
        
        # 시스템 상태
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("✅ AutoSwingTradeSystem 초기화 완료")
    
    def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            self.logger.info("🚀 AutoSwingTrade 시스템 초기화 시작...")
            
            # 1. 설정 검증
            if not validate_settings():
                self.logger.error("❌ 설정 검증 실패")
                return False
            
            # 2. 매매 봇 초기화
            self.trading_bot = TradingBot(self.message_queue, self.command_queue)
            if not self.trading_bot.initialize():
                self.logger.error("❌ 매매 봇 초기화 실패")
                return False
            
            # 3. 텔레그램 봇 초기화 (설정이 활성화된 경우만)
            settings = get_settings()
            telegram_enabled = settings.get_telegram_bool('enabled', False) if settings else False
            
            if telegram_enabled and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    self.telegram_bot = TelegramBot(self.message_queue, self.command_queue)
                    if not self.telegram_bot.initialize():
                        self.logger.warning("⚠️ 텔레그램 봇 초기화 실패 - 매매봇만 실행")
                        self.telegram_bot = None
                    else:
                        self.logger.info("✅ 텔레그램 봇 초기화 완료")
                except Exception as e:
                    self.logger.error(f"❌ 텔레그램 봇 초기화 중 오류: {e}")
                    self.telegram_bot = None
            else:
                if not telegram_enabled:
                    self.logger.info("ℹ️ 텔레그램 봇이 비활성화되어 있습니다 (enabled=false)")
                elif not TELEGRAM_BOT_TOKEN:
                    self.logger.info("ℹ️ 텔레그램 봇 토큰이 설정되지 않았습니다")
                elif not TELEGRAM_CHAT_ID:
                    self.logger.info("ℹ️ 텔레그램 채팅 ID가 설정되지 않았습니다")
                self.logger.info("ℹ️ 텔레그램 봇 없이 매매봇만 실행합니다")
            
            self.logger.info("✅ 시스템 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 시스템 초기화 실패: {e}")
            return False
    
    def start(self) -> bool:
        """시스템 시작"""
        try:
            if self.is_running:
                self.logger.warning("⚠️ 시스템이 이미 실행 중입니다")
                return False
            
            self.logger.info("🚀 AutoSwingTrade 시스템 시작...")
            self.is_running = True
            self.start_time = now_kst()
            
            # 1. 매매 봇 시작
            if not self.trading_bot.start():
                self.logger.error("❌ 매매 봇 시작 실패")
                return False
            
            # 2. 텔레그램 봇 시작 (있는 경우)
            if self.telegram_bot:
                if not self.telegram_bot.start():
                    self.logger.warning("⚠️ 텔레그램 봇 시작 실패")
            
            self.logger.info("✅ 시스템 시작 완료")
            self._print_system_info()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 시스템 시작 실패: {e}")
            self.is_running = False
            return False
    
    def stop(self) -> bool:
        """시스템 정지"""
        try:
            if not self.is_running:
                self.logger.warning("⚠️ 시스템이 실행 중이 아닙니다")
                return False
            
            self.logger.info("🛑 AutoSwingTrade 시스템 정지 중...")
            self.is_running = False
            
            # 1. 매매 봇 정지
            if self.trading_bot:
                self.trading_bot.stop()
            
            # 2. 텔레그램 봇 정지
            if self.telegram_bot:
                self.telegram_bot.stop()
            
            self.logger.info("✅ 시스템 정지 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 시스템 정지 실패: {e}")
            return False
    
    def run(self) -> None:
        """시스템 실행 (메인 루프)"""
        try:
            # 시스템 시작
            if not self.start():
                sys.exit(1)
            
            # 메인 루프
            while self.is_running:
                try:
                    # 시스템 상태 모니터링
                    self._monitor_system()
                    
                    # 1초 대기
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("🔄 사용자 중단 요청")
                    break
                except Exception as e:
                    self.logger.error(f"❌ 메인 루프 오류: {e}")
                    time.sleep(5)
            
        except Exception as e:
            self.logger.error(f"❌ 시스템 실행 오류: {e}")
        finally:
            self.stop()
    
    def _monitor_system(self) -> None:
        """시스템 상태 모니터링"""
        try:
            # 매매 봇 상태 확인
            if self.trading_bot and not self.trading_bot.is_running:
                self.logger.warning("⚠️ 매매 봇이 정지되었습니다")
            
            # 텔레그램 봇 상태 확인
            if self.telegram_bot and not self.telegram_bot.is_running:
                self.logger.warning("⚠️ 텔레그램 봇이 정지되었습니다")
                
        except Exception as e:
            self.logger.error(f"❌ 시스템 모니터링 오류: {e}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """시그널 핸들러"""
        self.logger.info(f"🔄 시그널 수신: {signum}")
        self.is_running = False
    
    def _print_system_info(self) -> None:
        """시스템 정보 출력"""
        print("\n" + "="*60)
        print("🚀 AutoSwingTrade 시스템 실행 중")
        print("="*60)
        print(f"📅 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 매매 봇: {'✅ 실행중' if self.trading_bot and self.trading_bot.is_running else '❌ 정지'}")
        print(f"📱 텔레그램 봇: {'✅ 실행중' if self.telegram_bot and self.telegram_bot.is_running else '❌ 정지'}")
        print("\n💡 시스템 제어:")
        print("  - Ctrl+C: 시스템 종료")
        if self.telegram_bot:
            print("  - 텔레그램 명령어: /start, /stop, /status, /help")
        print("="*60)
        print()


def main():
    """메인 함수"""
    print("🚀 AutoSwingTrade 시스템 시작")
    print("="*50)
    
    # 시스템 생성 및 실행
    system = AutoSwingTradeSystem()
    
    try:
        # 시스템 초기화
        if not system.initialize():
            print("❌ 시스템 초기화 실패")
            sys.exit(1)
        
        # 시스템 실행
        system.run()
        
    except KeyboardInterrupt:
        print("\n🔄 사용자 중단 요청")
    except Exception as e:
        print(f"\n❌ 시스템 실행 오류: {e}")
    finally:
        print("\n🛑 AutoSwingTrade 시스템 종료")
        sys.exit(0)


if __name__ == "__main__":
    main() 