"""
텔레그램 봇 클래스

매매 봇과 큐를 통해 통신하며 원격 제어 및 알림 기능을 제공합니다.
"""
import time
import queue
import threading
import html
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests
import json

from utils.logger import setup_logger
from utils.korean_time import now_kst
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramBot:
    """텔레그램 봇 클래스"""
    
    def __init__(self, message_queue: queue.Queue, command_queue: queue.Queue):
        """
        텔레그램 봇 초기화
        
        Args:
            message_queue: 매매 봇으로부터 메시지를 받는 큐
            command_queue: 매매 봇으로 명령을 보내는 큐
        """
        self.logger = setup_logger(__name__)
        self.message_queue = message_queue
        self.command_queue = command_queue
        
        # 봇 설정
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # 상태 관리
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0
        
        # 통계
        self.stats = {
            'messages_sent': 0,
            'commands_received': 0,
            'errors': 0,
            'start_time': None,
            'last_activity': None
        }
        
        self.logger.info("✅ TelegramBot 초기화 완료")
    
    def initialize(self) -> bool:
        """텔레그램 봇 초기화"""
        try:
            if not self.bot_token or not self.chat_id:
                self.logger.error("❌ 텔레그램 봇 토큰 또는 채팅 ID가 없습니다")
                return False
            
            # 봇 정보 확인
            if not self._test_bot_connection():
                self.logger.error("❌ 텔레그램 봇 연결 테스트 실패")
                return False
            
            self.logger.info("✅ 텔레그램 봇 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 봇 초기화 실패: {e}")
            return False
    
    def start(self) -> bool:
        """텔레그램 봇 시작"""
        if self.is_running:
            self.logger.warning("⚠️ 텔레그램 봇이 이미 실행 중입니다")
            return False
        
        try:
            self.is_running = True
            self.stats['start_time'] = now_kst()
            
            # 메시지 처리 스레드 시작
            self.thread = threading.Thread(target=self._bot_loop, daemon=True)
            self.thread.start()
            
            # 시작 메시지 전송
            start_message = "🚀 AutoSwingTrade 시스템이 시작되었습니다!"
            self._send_telegram_message(start_message)
            
            self.logger.info("🚀 텔레그램 봇 시작")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 봇 시작 실패: {e}")
            self.is_running = False
            return False
    
    def stop(self) -> bool:
        """텔레그램 봇 정지"""
        if not self.is_running:
            self.logger.warning("⚠️ 텔레그램 봇이 실행 중이 아닙니다")
            return False
        
        try:
            self.is_running = False
            
            # 스레드 종료 대기
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            # 종료 메시지 전송
            stop_message = "🛑 AutoSwingTrade 시스템이 종료되었습니다."
            self._send_telegram_message(stop_message)
            
            self.logger.info("🛑 텔레그램 봇 정지")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 봇 정지 실패: {e}")
            return False
    
    def _bot_loop(self) -> None:
        """텔레그램 봇 메인 루프"""
        self.logger.info("🔄 텔레그램 봇 루프 시작")
        
        while self.is_running:
            try:
                # 1. 매매 봇으로부터 메시지 처리
                self._process_messages()
                
                # 2. 텔레그램 업데이트 확인
                self._check_telegram_updates()
                
                # 3. 대기
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"❌ 텔레그램 봇 루프 오류: {e}")
                self.stats['errors'] += 1
                time.sleep(5)
        
        self.logger.info("🔄 텔레그램 봇 루프 종료")
    
    def _process_messages(self) -> None:
        """매매 봇으로부터 메시지 처리"""
        try:
            while not self.message_queue.empty():
                message_data = self.message_queue.get_nowait()
                self._handle_message(message_data)
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"❌ 메시지 처리 오류: {e}")
    
    def _handle_message(self, message_data: Dict[str, Any]) -> None:
        """개별 메시지 처리"""
        try:
            message_type = message_data.get('type', 'info')
            message = message_data.get('message', '')
            timestamp = message_data.get('timestamp', now_kst())
            
            # 특별한 메시지 타입 처리
            if message_type == 'status_response':
                # 상태 정보 응답
                status_data = message_data.get('data', {})
                formatted_message = self._format_trading_bot_status(status_data)
                self._send_telegram_message(formatted_message)
                return
            
            elif message_type == 'candidates_response':
                # 매수후보 종목 응답
                candidates_data = message_data.get('data', [])
                formatted_message = self._format_candidates_message(candidates_data)
                self._send_telegram_message(formatted_message)
                return
            
            # 일반 메시지 처리
            # 메시지 타입별 아이콘 추가
            if message_type == 'error':
                formatted_message = f"❌ {message}"
            elif message_type == 'warning':
                formatted_message = f"⚠️ {message}"
            elif message_type == 'success':
                formatted_message = f"✅ {message}"
            elif message_type == 'order':
                formatted_message = f"📋 {message}"
            elif message_type == 'trade':
                formatted_message = f"💰 {message}"
            else:
                formatted_message = f"ℹ️ {message}"
            
            # 시간 정보 추가
            time_str = timestamp.strftime('%H:%M:%S')
            final_message = f"[{time_str}] {formatted_message}"
            
            # 텔레그램으로 전송
            self._send_telegram_message(final_message)
            
        except Exception as e:
            self.logger.error(f"❌ 메시지 처리 오류: {e}")
    
    def _check_telegram_updates(self) -> None:
        """텔레그램 업데이트 확인"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'limit': 10,
                'timeout': 1
            }
            
            # 타임아웃 시간을 늘리고 재시도 로직 추가
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, timeout=15)  # 5초 -> 15초로 증가
                    if response.status_code == 200:
                        data = response.json()
                        if data['ok']:
                            for update in data['result']:
                                self._process_telegram_update(update)
                                self.last_update_id = update['update_id']
                        break  # 성공하면 재시도 루프 종료
                    else:
                        self.logger.warning(f"⚠️ 텔레그램 API 응답 오류: {response.status_code}")
                        if attempt < max_retries - 1:
                            time.sleep(1)  # 재시도 전 1초 대기
                            continue
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 API 타임아웃 (재시도 {attempt + 1}/{max_retries})")
                        time.sleep(2)  # 재시도 전 2초 대기
                        continue
                    else:
                        self.logger.warning("⚠️ 텔레그램 API 타임아웃 - 최대 재시도 횟수 초과")
                        break
                        
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 API 연결 오류 (재시도 {attempt + 1}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        raise  # 마지막 시도에서는 예외를 다시 발생시킴
                        
        except Exception as e:
            # 심각한 오류만 에러로 로깅, 일시적 네트워크 문제는 경고로 처리
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                self.logger.warning(f"⚠️ 텔레그램 연결 일시 중단: {e}")
            else:
                self.logger.error(f"❌ 텔레그램 업데이트 확인 오류: {e}")
    
    def _process_telegram_update(self, update: Dict[str, Any]) -> None:
        """텔레그램 업데이트 처리"""
        try:
            if 'message' not in update:
                return
            
            message = update['message']
            chat_id = str(message['chat']['id'])
            
            # 허용된 채팅 ID 확인
            if chat_id != self.chat_id:
                self.logger.warning(f"⚠️ 허용되지 않은 채팅 ID: {chat_id}")
                return
            
            if 'text' not in message:
                return
            
            text = message['text'].strip()
            self.stats['commands_received'] += 1
            self.stats['last_activity'] = now_kst()
            
            # 명령어 처리
            self._handle_telegram_command(text)
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 업데이트 처리 오류: {e}")
    
    def _handle_telegram_command(self, command: str) -> None:
        """텔레그램 명령어 처리"""
        try:
            command = command.lower()
            
            if command == '/start':
                self._send_telegram_message(self._get_help_message())
            
            elif command == '/help':
                self._send_telegram_message(self._get_help_message())
            
            elif command == '/status':
                self.command_queue.put({'type': 'status'})
                self._send_telegram_message("📊 매매 봇 상태 조회 중...")
            
            elif command == '/stop':
                self.command_queue.put({'type': 'stop'})
                self._send_telegram_message("🛑 매매 봇 정지 명령을 전송했습니다.")
            
            elif command == '/pause':
                self.command_queue.put({'type': 'pause'})
                self._send_telegram_message("⏸️ 매매 봇 일시정지 명령을 전송했습니다.")
            
            elif command == '/resume':
                self.command_queue.put({'type': 'resume'})
                self._send_telegram_message("▶️ 매매 봇 재개 명령을 전송했습니다.")
            
            elif command == '/screening':
                self.command_queue.put({'type': 'screening'})
                self._send_telegram_message("🔍 수동 스크리닝 명령을 전송했습니다.")
            
            elif command == '/candidates':
                self.command_queue.put({'type': 'candidates'})
                self._send_telegram_message("🎯 매수후보 종목 조회 중...")
            
            elif command == '/stats':
                self._send_telegram_message(self._get_bot_stats())
            
            else:
                self._send_telegram_message(f"❓ 알 수 없는 명령어: {command}\n/help 명령어로 도움말을 확인하세요.")
                
        except Exception as e:
            self.logger.error(f"❌ 명령어 처리 오류: {e}")
    
    def _send_telegram_message(self, message: str) -> bool:
        """텔레그램 메시지 전송"""
        try:
            url = f"{self.api_url}/sendMessage"
            
            # 먼저 일반 텍스트로 전송 시도
            data = {
                'chat_id': self.chat_id,
                'text': message
            }
            
            # 재시도 로직 추가
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, data=data, timeout=15)  # 10초 -> 15초로 증가
                    if response.status_code == 200:
                        result = response.json()
                        if result['ok']:
                            self.stats['messages_sent'] += 1
                            return True
                        else:
                            self.logger.error(f"❌ 텔레그램 메시지 전송 실패: {result}")
                            return False
                    else:
                        # 상세한 오류 정보 로깅
                        try:
                            error_data = response.json()
                            self.logger.error(f"❌ 텔레그램 API 오류 {response.status_code}: {error_data}")
                            
                            # 400 오류인 경우 메시지 내용도 로깅
                            if response.status_code == 400:
                                self.logger.error(f"❌ 전송 실패한 메시지: {message[:100]}...")
                                
                        except:
                            self.logger.error(f"❌ 텔레그램 API 오류 {response.status_code}: {response.text}")
                        return False
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 메시지 전송 타임아웃 (재시도 {attempt + 1}/{max_retries})")
                        time.sleep(2)
                        continue
                    else:
                        self.logger.warning("⚠️ 텔레그램 메시지 전송 타임아웃 - 최대 재시도 횟수 초과")
                        return False
                        
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 메시지 전송 연결 오류 (재시도 {attempt + 1}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        raise
            
            return False  # 모든 재시도가 실패한 경우
                
        except Exception as e:
            # 네트워크 관련 오류는 경고로, 기타 오류는 에러로 처리
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                self.logger.warning(f"⚠️ 텔레그램 메시지 전송 일시 중단: {e}")
            else:
                self.logger.error(f"❌ 텔레그램 메시지 전송 오류: {e}")
            return False
    
    def _test_bot_connection(self) -> bool:
        """봇 연결 테스트"""
        try:
            url = f"{self.api_url}/getMe"
            
            # 재시도 로직 추가
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, timeout=15)  # 10초 -> 15초로 증가
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data['ok']:
                            bot_info = data['result']
                            self.logger.info(f"✅ 텔레그램 봇 연결 성공: {bot_info['first_name']} (@{bot_info['username']})")
                            return True
                        else:
                            self.logger.error(f"❌ 텔레그램 봇 API 오류: {data}")
                            return False
                    else:
                        try:
                            error_data = response.json()
                            self.logger.error(f"❌ 텔레그램 API HTTP 오류 {response.status_code}: {error_data}")
                            
                            # 401 오류인 경우 토큰 문제 안내
                            if response.status_code == 401:
                                self.logger.error("🔧 텔레그램 봇 토큰이 잘못되었습니다. config/key.ini 파일의 token 값을 확인해주세요.")
                                
                        except:
                            self.logger.error(f"❌ 텔레그램 API HTTP 오류 {response.status_code}: {response.text}")
                        return False
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 봇 연결 테스트 타임아웃 (재시도 {attempt + 1}/{max_retries})")
                        time.sleep(2)
                        continue
                    else:
                        self.logger.warning("⚠️ 텔레그램 봇 연결 테스트 타임아웃 - 최대 재시도 횟수 초과")
                        return False
                        
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ 텔레그램 봇 연결 테스트 오류 (재시도 {attempt + 1}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        raise
            
            return False  # 모든 재시도가 실패한 경우
                
        except Exception as e:
            # 네트워크 관련 오류는 경고로, 기타 오류는 에러로 처리
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                self.logger.warning(f"⚠️ 텔레그램 봇 연결 일시 중단: {e}")
            else:
                self.logger.error(f"❌ 텔레그램 봇 연결 테스트 오류: {e}")
            return False
    
    def _get_help_message(self) -> str:
        """도움말 메시지 생성"""
        return """
🤖 AutoSwingTrade 텔레그램 봇

📋 사용 가능한 명령어:

🔹 /start - 봇 시작 및 도움말
🔹 /help - 도움말 보기
🔹 /status - 매매 봇 상태 확인
🔹 /stop - 매매 봇 정지
🔹 /pause - 매매 봇 일시정지
🔹 /resume - 매매 봇 재개
🔹 /screening - 수동 스크리닝 실행
🔹 /candidates - 매수후보 종목 조회
🔹 /stats - 텔레그램 봇 통계

💡 알림 기능:
• 매매 신호 및 주문 실행 알림
• 시스템 상태 변경 알림
• 오류 및 경고 메시지 알림

⚠️ 주의사항:
• 실전 매매 시스템이므로 신중하게 사용하세요
• 시스템 종료는 /stop 명령어를 사용하세요
        """.strip()
    
    def _get_bot_stats(self) -> str:
        """봇 통계 메시지 생성"""
        try:
            uptime = ""
            if self.stats['start_time']:
                uptime_delta = now_kst() - self.stats['start_time']
                hours = int(uptime_delta.total_seconds() // 3600)
                minutes = int((uptime_delta.total_seconds() % 3600) // 60)
                uptime = f"{hours}시간 {minutes}분"
            
            return f"""
📊 텔레그램 봇 통계

🕐 실행 시간: {uptime}
📤 전송 메시지: {self.stats['messages_sent']}개
📥 수신 명령: {self.stats['commands_received']}개
❌ 오류 횟수: {self.stats['errors']}개
🔄 최근 활동: {self.stats['last_activity'].strftime('%H:%M:%S') if self.stats['last_activity'] else 'N/A'}
            """.strip()
            
        except Exception as e:
            self.logger.error(f"❌ 봇 통계 생성 오류: {e}")
            return "❌ 통계 정보를 가져올 수 없습니다."
    
    def _format_trading_bot_status(self, status: Dict[str, Any]) -> str:
        """매매 봇 상태 정보 포맷팅"""
        try:
            return f"""
📊 매매 봇 상태

🔄 상태: {status.get('status', 'N/A')}
🏢 장 상태: {status.get('market_status', 'N/A')}
⚡ 실행 중: {'예' if status.get('is_running', False) else '아니오'}
📈 보유 종목: {status.get('positions_count', 0)}개
📊 총 거래: {status.get('stats', {}).get('total_trades', 0)}회
🎯 성공률: {status.get('stats', {}).get('win_rate', 0):.1f}%
💰 총 손익: {status.get('stats', {}).get('total_profit_loss', 0):+,.0f}원
🕐 최종 업데이트: {status.get('last_update', 'N/A')}
            """.strip()
        except Exception as e:
            self.logger.error(f"❌ 매매 봇 상태 포맷팅 오류: {e}")
            return "❌ 상태 정보를 가져올 수 없습니다."
    
    def _format_candidates_message(self, candidates: List[Dict[str, Any]]) -> str:
        """매수후보 종목 메시지 포맷팅"""
        try:
            if not candidates:
                return "📋 현재 매수후보 종목이 없습니다."
            
            message = "🎯 매수후보 종목 (상위 10개)\n\n"
            
            for i, candidate in enumerate(candidates[:10], 1):
                stock_name = candidate.get('stock_name', 'N/A')
                stock_code = candidate.get('stock_code', 'N/A')
                pattern_type = candidate.get('pattern_type', 'N/A')
                confidence = candidate.get('confidence', 0)
                current_price = candidate.get('current_price', 0)
                
                message += f"{i}. {stock_name} ({stock_code})\n"
                message += f"   📊 패턴: {pattern_type}\n"
                message += f"   🎯 신뢰도: {confidence:.1f}%\n"
                message += f"   💰 현재가: {current_price:,.0f}원\n\n"
            
            return message.strip()
            
        except Exception as e:
            self.logger.error(f"❌ 매수후보 종목 포맷팅 오류: {e}")
            return "❌ 매수후보 종목 정보를 가져올 수 없습니다." 