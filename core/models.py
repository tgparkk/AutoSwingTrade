"""
주식 자동매매 시스템 데이터 모델 정의

모든 데이터클래스를 중앙에서 관리합니다.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from .enums import SignalType, OrderType, PositionStatus, TradingMode, RiskLevel, OrderStatus


@dataclass
class TradingConfig:
    """매매 설정 정보"""
    max_position_count: int = 10  # 최대 보유 종목 수
    max_position_ratio: float = 0.2  # 종목당 최대 투자 비율 (20%)
    min_position_ratio: float = 0.1  # 종목당 최소 투자 비율 (10%)
    stop_loss_ratio: float = -0.01  # 손절 비율 (-1%)
    take_profit_ratio: float = 0.03  # 익절 비율 (3%)
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
    take_profit_price: Optional[float] = None
    entry_reason: str = ""
    notes: str = ""
    target_price: Optional[float] = None  # 목표가
    partial_sold: bool = False  # 부분 매도 완료 여부


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
    take_profit_price: Optional[float] = None
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
        """주문이 만료되었는지 확인"""
        from datetime import timedelta
        timeout = timedelta(minutes=self.timeout_minutes)
        return (datetime.now() - self.order_time) > timeout
    
    @property
    def is_partially_filled(self) -> bool:
        """부분 체결되었는지 확인"""
        return self.filled_quantity > 0 and self.remaining_quantity > 0
    
    @property
    def is_fully_filled(self) -> bool:
        """완전 체결되었는지 확인"""
        return self.remaining_quantity == 0 and self.filled_quantity == self.quantity


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