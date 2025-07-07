"""
한국 시간 관련 유틸리티
"""
from datetime import datetime, timedelta
from typing import Optional
import pytz


KST = pytz.timezone('Asia/Seoul')


def now_kst() -> datetime:
    """현재 한국 시간 반환"""
    return datetime.now(KST)


def to_kst(dt: datetime) -> datetime:
    """UTC 시간을 한국 시간으로 변환"""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(KST)


def ensure_kst(dt: datetime) -> datetime:
    """
    datetime 객체를 KST로 안전하게 변환
    
    Args:
        dt: 변환할 datetime 객체
        
    Returns:
        datetime: KST timezone 정보가 있는 datetime 객체
    """
    if dt.tzinfo is None:
        # timezone 정보가 없으면 KST로 가정하고 변환
        return KST.localize(dt)
    else:
        # 이미 timezone 정보가 있으면 KST로 변환
        return dt.astimezone(KST)


def safe_datetime_subtract(dt1: datetime, dt2: datetime) -> timedelta:
    """
    timezone 정보가 다른 datetime 객체들 간의 안전한 뺄셈 연산
    
    Args:
        dt1: 첫 번째 datetime (minuend)
        dt2: 두 번째 datetime (subtrahend)
        
    Returns:
        timedelta: dt1 - dt2 결과
    """
    # 둘 다 KST로 통일
    dt1_kst = ensure_kst(dt1)
    dt2_kst = ensure_kst(dt2)
    
    return dt1_kst - dt2_kst


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """장 운영 시간 확인"""
    if dt is None:
        dt = now_kst()
    
    # 주말 체크
    if dt.weekday() >= 5:  # 토(5), 일(6)
        return False
    
    # 장 시간 체크 (09:00 ~ 15:30)
    market_open = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = dt.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= dt <= market_close


def is_pre_market(dt: Optional[datetime] = None) -> bool:
    """장전 시간 확인 (08:00 ~ 09:00)"""
    if dt is None:
        dt = now_kst()
    
    if dt.weekday() >= 5:
        return False
    
    pre_market_start = dt.replace(hour=8, minute=0, second=0, microsecond=0)
    market_open = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return pre_market_start <= dt < market_open


def is_after_market(dt: Optional[datetime] = None) -> bool:
    """장후 시간 확인 (15:30 ~ 18:00)"""
    if dt is None:
        dt = now_kst()
    
    if dt.weekday() >= 5:
        return False
    
    market_close = dt.replace(hour=15, minute=30, second=0, microsecond=0)
    after_market_end = dt.replace(hour=18, minute=0, second=0, microsecond=0)
    
    return market_close < dt <= after_market_end


def next_market_open() -> datetime:
    """다음 장 시작 시간 반환"""
    now = now_kst()
    
    # 오늘 장 시작 시간
    today_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # 오늘 장이 아직 시작하지 않았으면
    if now < today_open and now.weekday() < 5:
        return today_open
    
    # 다음 영업일 찾기
    next_day = now + timedelta(days=1)
    while next_day.weekday() >= 5:  # 주말 건너뛰기
        next_day += timedelta(days=1)
    
    return next_day.replace(hour=9, minute=0, second=0, microsecond=0)


def get_trading_day_count(start_date: datetime, end_date: datetime) -> int:
    """거래일 수 계산 (주말 제외)"""
    current = start_date.date()
    end = end_date.date()
    days = 0
    
    while current <= end:
        if current.weekday() < 5:  # 평일만
            days += 1
        current += timedelta(days=1)
    
    return days


def format_kst(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """한국 시간 포맷팅"""
    if dt.tzinfo is None:
        dt = KST.localize(dt)
    return dt.strftime(format_str)


# ---------------------------------------------------------------------------
# 객체 지향 래퍼 클래스 (기존 함수 사용)
# ---------------------------------------------------------------------------
class KoreanTime:
    """한국 주식 시장 시간 관련 헬퍼 클래스

    기존 모듈 내 각종 함수들을 객체 지향 형태로 감싸서 제공합니다.
    스레드나 컨트롤러에서 인스턴스 형태로 사용하기 용이하도록 구현했습니다.
    """

    # 현재 시각 -------------------------------------------------------------
    @staticmethod
    def now() -> datetime:
        """현재 한국 시각(KST) 반환"""
        return now_kst()

    # 시장 상태 ------------------------------------------------------------
    def is_market_time(self, dt: Optional[datetime] = None) -> bool:
        """정규장(09:00~15:30) 여부 확인"""
        return is_market_open(dt)

    def is_pre_market(self, dt: Optional[datetime] = None) -> bool:
        """장전(08:00~09:00) 여부 확인"""
        return is_pre_market(dt)

    def is_after_market(self, dt: Optional[datetime] = None) -> bool:
        """장후(15:30~18:00) 여부 확인"""
        return is_after_market(dt)

    def next_market_open(self) -> datetime:
        """다음 장 시작 시각 반환"""
        return next_market_open()

    # 유틸리티 -------------------------------------------------------------
    @staticmethod
    def to_kst(dt: datetime) -> datetime:
        """임의 datetime을 한국 시각으로 변환"""
        return to_kst(dt)

    @staticmethod
    def format(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """포맷된 문자열 반환"""
        return format_kst(dt, fmt)


class KoreanTimeManager(KoreanTime):
    """기존 코드 호환성을 위한 별칭 클래스

    KoreanTime 과 동일 기능을 제공하며, 과거 코드에서 사용되던
    `KoreanTimeManager` 명칭을 유지하기 위해 별도로 선언합니다.
    """

    def is_trading_day(self, dt: Optional[datetime] = None) -> bool:
        """거래일 여부 확인 (주말 제외)"""
        if dt is None:
            dt = self.now()
        
        # 주말 체크
        return dt.weekday() < 5  # 월(0) ~ 금(4)
    
    def is_market_open(self, dt: Optional[datetime] = None) -> bool:
        """장 운영 시간 확인"""
        return self.is_market_time(dt) 