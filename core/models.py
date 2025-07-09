"""
주식 자동매매 시스템 데이터 모델 정의

모든 데이터클래스를 중앙에서 관리합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from .enums import SignalType, OrderType, PositionStatus, TradingMode, RiskLevel, OrderStatus, PatternType


@dataclass
class TradingConfig:
    """매매 설정 정보"""
    max_position_count: int = 10  # 최대 보유 종목 수
    max_position_ratio: float = 0.2  # 종목당 최대 투자 비율 (20%)
    min_position_ratio: float = 0.1  # 종목당 최소 투자 비율 (10%)
    stop_loss_ratio: float = -0.01  # 손절 비율 (-1%)
    take_profit_ratio: float = 0.03  # 익절 비율 (3%) - 보수적으로 조정
    trading_start_time: str = "09:00"  # 매매 시작 시간
    trading_end_time: str = "15:20"  # 매매 종료 시간
    check_interval: int = 10  # 체크 간격 (초)
    trading_mode: TradingMode = TradingMode.MODERATE  # 매매 모드
    risk_level: RiskLevel = RiskLevel.MEDIUM  # 리스크 수준
    enable_auto_trading: bool = True  # 자동 매매 활성화
    enable_risk_management: bool = True  # 리스크 관리 활성화
    max_daily_loss: float = 0.03  # 일일 최대 손실률 (3%)
    max_daily_trades: int = 50  # 일일 최대 거래 횟수
    test_mode: bool = False  # 테스트 모드 (시간 제한 우회)
    
    # 시간 기반 매도 조건 추가
    max_holding_days: int = 10  # 최대 보유 기간 (일)
    enable_time_based_exit: bool = True  # 시간 기반 매도 활성화
    sideways_exit_days: int = 5  # 횡보 구간 매도 기간 (일)
    sideways_threshold: float = 0.02  # 횡보 판단 임계값 (2%)
    partial_exit_days: int = 7  # 부분 매도 시작 기간 (일)
    partial_exit_ratio: float = 0.5  # 부분 매도 비율 (50%)


@dataclass
class Position:
    """포지션 정보"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float
    current_price: float
    profit_loss: float
    profit_loss_rate: float
    entry_time: datetime
    last_update: datetime
    status: PositionStatus = PositionStatus.ACTIVE
    order_type: OrderType = OrderType.LIMIT
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None  # 익절 목표가 (절대값, 패턴 분석 기반)
    entry_reason: str = ""
    notes: str = ""
    partial_sold: bool = False  # 부분 매도 완료 여부
    pattern_type: Optional[PatternType] = None  # 진입 패턴 타입 (패턴별 전략 적용용)
    market_cap_type: Optional[str] = None  # 시가총액 분류 (large_cap, mid_cap, small_cap)
    pattern_strength: Optional[float] = None  # 패턴 강도 (1.0 ~ 3.0)
    volume_ratio: Optional[float] = None  # 거래량 증가 배수


@dataclass
class TradingSignal:
    """매매 신호"""
    stock_code: str
    stock_name: str
    signal_type: SignalType
    price: float
    quantity: int
    reason: str
    confidence: float  # 신호 신뢰도 (0.0 ~ 1.0)
    timestamp: datetime
    order_type: OrderType = OrderType.LIMIT
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None  # 익절 목표가 (절대값, 패턴 분석 기반)
    valid_until: Optional[datetime] = None
    priority: int = 0  # 우선순위 (높을수록 우선)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeRecord:
    """거래 기록"""
    timestamp: datetime
    trade_type: str  # "BUY" or "SELL"
    stock_code: str
    stock_name: str
    quantity: int
    price: float
    amount: float
    reason: str
    order_id: str
    success: bool
    message: str
    commission: float = 0.0
    tax: float = 0.0
    net_amount: float = 0.0
    profit_loss: Optional[float] = None
    execution_time: Optional[datetime] = None


@dataclass
class AccountSnapshot:
    """계좌 스냅샷"""
    timestamp: datetime
    total_value: float
    available_amount: float
    stock_value: float
    cash_balance: float
    profit_loss: float
    profit_loss_rate: float
    position_count: int
    daily_trades: int
    daily_profit_loss: float


@dataclass
class MarketData:
    """시장 데이터"""
    stock_code: str
    stock_name: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    change_amount: float
    change_rate: float
    timestamp: datetime
    market_cap: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    eps: Optional[float] = None


@dataclass
class TechnicalIndicator:
    """기술적 지표"""
    stock_code: str
    timestamp: datetime
    sma_5: Optional[float] = None
    sma_20: Optional[float] = None
    sma_60: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    rsi: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    volume_ma: Optional[float] = None


@dataclass
class RiskMetrics:
    """리스크 지표"""
    timestamp: datetime
    portfolio_value: float
    var_1d: float  # 1일 VaR
    var_5d: float  # 5일 VaR
    max_drawdown: float  # 최대 손실률
    sharpe_ratio: float  # 샤프 비율
    volatility: float  # 변동성
    beta: float  # 베타
    correlation_kospi: float  # 코스피 상관계수
    concentration_risk: float  # 집중도 리스크
    sector_exposure: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """전략 설정"""
    name: str
    description: str
    enabled: bool = True
    weight: float = 1.0  # 전략 가중치
    parameters: Dict[str, Any] = field(default_factory=dict)
    min_confidence: float = 0.6  # 최소 신뢰도
    max_positions: int = 5  # 전략별 최대 포지션
    risk_limit: float = 0.02  # 전략별 리스크 한도
    cooldown_period: int = 300  # 재신호 대기시간 (초)


@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profitable_trades: int
    average_win: float
    average_loss: float
    profit_factor: float
    trades: List[TradeRecord] = field(default_factory=list)


@dataclass
class AlertConfig:
    """알림 설정"""
    price_change_threshold: float = 0.05  # 가격 변동 알림 임계값
    profit_loss_threshold: float = 0.03  # 손익 알림 임계값
    volume_spike_threshold: float = 2.0  # 거래량 급증 알림 임계값
    enable_trade_alerts: bool = True  # 거래 알림 활성화
    enable_error_alerts: bool = True  # 오류 알림 활성화
    enable_market_alerts: bool = True  # 시장 알림 활성화
    quiet_hours_start: str = "22:00"  # 무음 시간 시작
    quiet_hours_end: str = "08:00"  # 무음 시간 종료


@dataclass
class PendingOrder:
    """대기 중인 주문 정보"""
    order_id: str
    stock_code: str
    stock_name: str
    signal_type: SignalType
    order_type: OrderType
    order_status: OrderStatus
    quantity: int
    price: float
    filled_quantity: int
    remaining_quantity: int
    order_time: datetime
    last_check_time: datetime
    original_signal: TradingSignal
    krx_fwdg_ord_orgno: str = ""  # KIS API 주문 조직번호
    order_data: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout_minutes: int = 3  # 주문 만료 시간 (분)
    cancel_reason: Optional[str] = None
    previous_filled_quantity: int = 0  # 이전 체결량 (부분 체결 추적용)
    
    @property
    def is_expired(self) -> bool:
        """
        주문이 만료되었는지 확인
        
        장 시작 전 주문의 경우 9시 이후부터 만료 시간을 계산합니다.
        테스트 모드에서는 기존 로직(주문 시간부터 직접 계산)을 사용합니다.
        
        주요 변경사항:
        - 현재 시간이 장 시작 전(09:00 이전)이면 절대 만료되지 않음
        - 장 시작 후에만 만료 시간 계산을 시작
        """
        from utils.korean_time import now_kst, is_before_market_open, get_market_open_today
        
        current_time = now_kst()
        timeout = timedelta(minutes=self.timeout_minutes)
        
        # 테스트 모드인지 확인 (메타데이터에서 확인)
        is_test_mode = self.order_data.get('test_mode', False)
        
        if is_test_mode:
            # 테스트 모드에서는 기존 로직 사용
            return (current_time - self.order_time) > timeout
        
        # 🔥 핵심 수정: 현재 시간이 장 시작 전이면 절대 만료되지 않음
        if is_before_market_open(current_time):
            return False
        
        # 🔥 장 시작 후에만 만료 시간 계산
        # 주문 시간이 장 시작 전이었다면, 장 시작 시간(9시)부터 만료 시간 계산
        if is_before_market_open(self.order_time):
            market_open_today = get_market_open_today()
            elapsed_time = current_time - market_open_today
        else:
            # 주문 시간이 장 시작 후였다면, 주문 시간부터 만료 시간 계산
            elapsed_time = current_time - self.order_time
        
        return elapsed_time > timeout
    
    @property
    def is_partially_filled(self) -> bool:
        """부분 체결되었는지 확인"""
        return self.filled_quantity > 0 and self.remaining_quantity > 0
    
    @property
    def is_fully_filled(self) -> bool:
        """완전 체결되었는지 확인"""
        return self.remaining_quantity == 0 and self.filled_quantity == self.quantity


@dataclass
class PatternTradingConfig:
    """패턴별 거래 전략 설정"""
    pattern_type: PatternType
    pattern_name: str
    base_confidence: float              # 기본 신뢰도
    
    # 보유기간 설정
    min_holding_days: int               # 최소 보유일
    max_holding_days: int               # 최대 보유일
    optimal_holding_days: int           # 최적 보유일
    
    # 목표 수익률 설정 (시가총액별)
    target_returns: Dict[str, Dict[str, float]]  # {"large_cap": {"min": 0.03, "base": 0.05, "max": 0.08}}
    
    # 손절 설정
    stop_loss_method: str               # 손절 방식 ("pattern_low", "body_low", "gap_fill" 등)
    max_loss_ratio: float               # 최대 손실률
    trailing_stop: bool                 # 트레일링 스탑 사용 여부
    
    # 진입 조건
    entry_timing: str                   # 진입 시점 ("immediate", "next_day", "confirmation")
    confirmation_required: bool         # 추가 확인 필요 여부
    volume_multiplier: float            # 거래량 증가 배수 요구사항
    
    # 종료 조건
    profit_taking_rules: List[Dict[str, Any]]  # 수익 실현 규칙
    time_based_exit: bool               # 시간 기반 종료
    momentum_exit: bool                 # 모멘텀 소실 시 종료


@dataclass
class SystemStatus:
    """시스템 상태"""
    timestamp: datetime
    trading_status: str
    market_status: str
    is_running: bool
    positions_count: int
    available_amount: float
    total_value: float
    daily_profit_loss: float
    api_call_count: int
    error_count: int
    last_trade_time: Optional[datetime] = None
    uptime: Optional[float] = None  # 가동 시간 (초)
    memory_usage: Optional[float] = None  # 메모리 사용량 (MB)
    cpu_usage: Optional[float] = None  # CPU 사용률 (%) 