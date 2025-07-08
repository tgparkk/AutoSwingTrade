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


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "주문중"
    FILLED = "체결완료"
    PARTIAL_FILLED = "부분체결"
    CANCELLED = "취소됨"
    FAILED = "실패"


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
    ORDER_FILLED = "체결완료"
    ORDER_CANCELLED = "주문취소"


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


class PatternType(Enum):
    """캔들패턴 타입 - 신뢰도 TOP 5"""
    MORNING_STAR = "morning_star"  # 샛별 (신뢰도 95%+)
    BULLISH_ENGULFING = "bullish_engulfing"  # 상승장악형 (신뢰도 90%+)
    THREE_WHITE_SOLDIERS = "three_white_soldiers"  # 세 백병 (신뢰도 85%+)
    ABANDONED_BABY = "abandoned_baby"  # 버려진 아기 (신뢰도 90%+)
    HAMMER = "hammer"  # 망치형 (신뢰도 75%+) 