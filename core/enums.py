"""
주식 자동매매 시스템 열거형 정의

모든 상태 및 타입 관련 열거형을 중앙에서 관리합니다.
"""
from enum import Enum


class TradingStatus(Enum):
    """매매 상태 열거형"""
    STOPPED = "정지"
    RUNNING = "실행중"
    PAUSED = "일시정지"
    ERROR = "오류"


class MarketStatus(Enum):
    """장 상태 열거형"""
    CLOSED = "장마감"
    OPEN = "장중"
    PRE_MARKET = "장전"
    AFTER_MARKET = "장후"


class SignalType(Enum):
    """매매 신호 타입"""
    BUY = "매수"
    SELL = "매도"
    HOLD = "보유"


class OrderType(Enum):
    """주문 타입"""
    MARKET = "시장가"
    LIMIT = "지정가"
    STOP_LOSS = "손절"
    TAKE_PROFIT = "익절"


class PositionStatus(Enum):
    """포지션 상태"""
    ACTIVE = "활성"
    CLOSED = "종료"
    PARTIAL = "부분체결"


class TradingMode(Enum):
    """매매 모드"""
    CONSERVATIVE = "보수적"
    MODERATE = "중간"
    AGGRESSIVE = "공격적"


class RiskLevel(Enum):
    """리스크 수준"""
    LOW = "낮음"
    MEDIUM = "보통"
    HIGH = "높음"
    VERY_HIGH = "매우높음"


class MessageType(Enum):
    """메시지 타입"""
    INFO = "정보"
    WARNING = "경고"
    ERROR = "오류"
    SUCCESS = "성공"
    TRADE = "거래"


class CommandType(Enum):
    """명령 타입"""
    START = "시작"
    STOP = "정지"
    PAUSE = "일시정지"
    RESUME = "재개"
    STATUS = "상태"
    POSITIONS = "포지션"
    BALANCE = "잔고"
    HISTORY = "기록" 