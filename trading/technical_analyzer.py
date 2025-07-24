"""
기술적 분석 도구 클래스

패턴별 거래 전략 설정과 기술적 지표 계산을 담당합니다.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from enum import Enum

from core.enums import PatternType
from core.models import Position, PatternTradingConfig
from utils.logger import setup_logger


class MarketCapType(Enum):
    """시가총액 분류"""
    LARGE_CAP = "large_cap"  # 2조원 이상
    MID_CAP = "mid_cap"  # 3천억원 ~ 2조원
    SMALL_CAP = "small_cap"  # 3천억원 미만


class TechnicalIndicators:
    """기술적 지표 데이터"""
    def __init__(self, rsi: float, macd: float, macd_signal: float, 
                 bb_upper: float, bb_middle: float, bb_lower: float,
                 atr: float, ma20: float, ma60: float, ma120: float,
                 # 모멘텀 지표 추가
                 ma20_breakout: bool = False, ma60_breakout: bool = False,
                 relative_strength: float = 0.0, 
                 high_52w_ratio: float = 0.0,
                 momentum_5d: float = 0.0, momentum_20d: float = 0.0):
        self.rsi = rsi
        self.macd = macd
        self.macd_signal = macd_signal
        self.bb_upper = bb_upper
        self.bb_middle = bb_middle
        self.bb_lower = bb_lower
        self.atr = atr
        self.ma20 = ma20
        self.ma60 = ma60
        self.ma120 = ma120
        
        # 모멘텀 지표
        self.ma20_breakout = ma20_breakout      # 20일선 돌파 여부
        self.ma60_breakout = ma60_breakout      # 60일선 돌파 여부
        self.relative_strength = relative_strength  # 상대강도(RS)
        self.high_52w_ratio = high_52w_ratio    # 52주 신고가 대비 위치
        self.momentum_5d = momentum_5d          # 5일 수익률
        self.momentum_20d = momentum_20d        # 20일 수익률


class TechnicalAnalyzer:
    """기술적 분석 도구 클래스"""
    
    # 시가총액 기준 (단위: 억원)
    LARGE_CAP_THRESHOLD = 20000  # 2조원
    MID_CAP_THRESHOLD = 3000  # 3천억원
    
    # 기존 목표값 계산 배수 (하위 호환성 유지)
    TARGET_MULTIPLIERS = {
        MarketCapType.LARGE_CAP: {"base": 0.04, "min": 0.03, "max": 0.06},      # 3-6%
        MarketCapType.MID_CAP: {"base": 0.06, "min": 0.04, "max": 0.08},       # 4-8%
        MarketCapType.SMALL_CAP: {"base": 0.08, "min": 0.06, "max": 0.10}      # 6-10%
    }
    
    # 패턴별 거래 전략 설정
    PATTERN_CONFIGS = {
        PatternType.MORNING_STAR: PatternTradingConfig(
            pattern_type=PatternType.MORNING_STAR,
            pattern_name="샛별",
            base_confidence=95.0,
            min_holding_days=0,  # 기존 3일 → 0일 (당일 매도 가능)
            max_holding_days=5,  # 기존 10일 → 5일
            optimal_holding_days=4,  # 기존 7일 → 4일
            target_returns={
                "large_cap": {"min": 0.015, "base": 0.025, "max": 0.04},     # 1.5% ~ 4%
                "mid_cap": {"min": 0.015, "base": 0.03, "max": 0.04},        # 1.5% ~ 4%
                "small_cap": {"min": 0.015, "base": 0.035, "max": 0.04}      # 1.5% ~ 4%
            },
            stop_loss_method="entry_based",  # 진입가 기준 손절
            max_loss_ratio=0.02,            # 2% 최대 손실 (손익비 2:1)
            trailing_stop=True,
            entry_timing="immediate",        # 패턴 완성 즉시
            confirmation_required=False,
            volume_multiplier=1.5,
            profit_taking_rules=[
                {"days": 0, "min_profit": 0.015, "partial_exit": 0.6},  # 1.5%에서 부분 익절
                {"days": 2, "min_profit": 0.025, "partial_exit": 0.8},  # 2.5%에서 부분 익절  
                {"days": 4, "min_profit": 0.035, "partial_exit": 1.0}   # 3.5%에서 완전 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.BULLISH_ENGULFING: PatternTradingConfig(
            pattern_type=PatternType.BULLISH_ENGULFING,
            pattern_name="상승장악형",
            base_confidence=90.0,
            min_holding_days=0,  # 기존 2일 → 0일 (당일 매도 가능)
            max_holding_days=5,  # 기존 7일 → 5일
            optimal_holding_days=3,  # 기존 5일 → 3일
            target_returns={
                "large_cap": {"min": 0.015, "base": 0.025, "max": 0.04},     # 1.5% ~ 4%
                "mid_cap": {"min": 0.015, "base": 0.03, "max": 0.04},        # 1.5% ~ 4%
                "small_cap": {"min": 0.015, "base": 0.035, "max": 0.04}      # 1.5% ~ 4%
            },
            stop_loss_method="entry_based",  # 진입가 기준 손절
            max_loss_ratio=0.02,            # 2% 최대 손실 (손익비 2:1)
            trailing_stop=True,
            entry_timing="next_day",        # 익일 시가 매수
            confirmation_required=False,
            volume_multiplier=1.3,
            profit_taking_rules=[
                {"days": 0, "min_profit": 0.015, "partial_exit": 0.6},  # 1.5%에서 부분 익절
                {"days": 1, "min_profit": 0.025, "partial_exit": 0.8},  # 2.5%에서 부분 익절
                {"days": 3, "min_profit": 0.035, "partial_exit": 1.0}   # 3.5%에서 완전 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.THREE_WHITE_SOLDIERS: PatternTradingConfig(
            pattern_type=PatternType.THREE_WHITE_SOLDIERS,
            pattern_name="세 백병",
            base_confidence=85.0,
            min_holding_days=0,  # 기존 3일 → 0일 (당일 매도 가능)
            max_holding_days=5,  # 기존 14일 → 5일
            optimal_holding_days=4,  # 기존 10일 → 4일
            target_returns={
                "large_cap": {"min": 0.015, "base": 0.025, "max": 0.04},     # 1.5% ~ 4%
                "mid_cap": {"min": 0.015, "base": 0.03, "max": 0.04},        # 1.5% ~ 4%
                "small_cap": {"min": 0.015, "base": 0.035, "max": 0.04}      # 1.5% ~ 4%
            },
            stop_loss_method="entry_based",  # 진입가 기준 손절
            max_loss_ratio=0.02,            # 2% 최대 손실 (손익비 2:1)
            trailing_stop=True,
            entry_timing="confirmation",     # 세 번째 백병 확정 후
            confirmation_required=False,
            volume_multiplier=1.3,
            profit_taking_rules=[
                {"days": 0, "min_profit": 0.015, "partial_exit": 0.6},  # 1.5%에서 부분 익절
                {"days": 2, "min_profit": 0.025, "partial_exit": 0.8},  # 2.5%에서 부분 익절
                {"days": 4, "min_profit": 0.035, "partial_exit": 1.0}   # 3.5%에서 완전 익절
            ],
            time_based_exit=True,
            momentum_exit=False  # 추세 패턴이므로 모멘텀 기반 종료 비활성화
        ),
        
        PatternType.ABANDONED_BABY: PatternTradingConfig(
            pattern_type=PatternType.ABANDONED_BABY,
            pattern_name="버려진 아기",
            base_confidence=90.0,
            min_holding_days=0,  # 기존 3일 → 0일 (당일 매도 가능)
            max_holding_days=5,  # 기존 12일 → 5일
            optimal_holding_days=4,  # 기존 8일 → 4일
            target_returns={
                "large_cap": {"min": 0.015, "base": 0.025, "max": 0.04},     # 1.5% ~ 4%
                "mid_cap": {"min": 0.015, "base": 0.03, "max": 0.04},        # 1.5% ~ 4%
                "small_cap": {"min": 0.015, "base": 0.035, "max": 0.04}      # 1.5% ~ 4%
            },
            stop_loss_method="entry_based",  # 진입가 기준 손절
            max_loss_ratio=0.02,            # 2% 최대 손실 (손익비 2:1)
            trailing_stop=True,
            entry_timing="immediate",        # 패턴 완성 즉시
            confirmation_required=False,
            volume_multiplier=2.0,           # 높은 거래량 요구
            profit_taking_rules=[
                {"days": 0, "min_profit": 0.015, "partial_exit": 0.6},  # 1.5%에서 부분 익절
                {"days": 2, "min_profit": 0.025, "partial_exit": 0.8},  # 2.5%에서 부분 익절
                {"days": 4, "min_profit": 0.035, "partial_exit": 1.0}   # 3.5%에서 완전 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.HAMMER: PatternTradingConfig(
            pattern_type=PatternType.HAMMER,
            pattern_name="망치형",
            base_confidence=75.0,
            min_holding_days=0,  # 기존 1일 → 0일 (당일 매도 가능)
            max_holding_days=3,  # 기존 5일 → 3일
            optimal_holding_days=2,  # 기존 3일 → 2일
            target_returns={
                "large_cap": {"min": 0.015, "base": 0.02, "max": 0.04},      # 1.5% ~ 4% (망치형은 보수적)
                "mid_cap": {"min": 0.015, "base": 0.025, "max": 0.04},       # 1.5% ~ 4%
                "small_cap": {"min": 0.015, "base": 0.03, "max": 0.04}       # 1.5% ~ 4%
            },
            stop_loss_method="entry_based",  # 진입가 기준 손절
            max_loss_ratio=0.015,            # 1.5% 최대 손실 (손익비 2:1)
            trailing_stop=False,
            entry_timing="confirmation",     # 익일 상승 확인 후 진입
            confirmation_required=True,
            volume_multiplier=1.2,
            profit_taking_rules=[
                {"days": 0, "min_profit": 0.015, "partial_exit": 0.6},  # 1.5%에서 부분 익절
                {"days": 1, "min_profit": 0.025, "partial_exit": 1.0}   # 2.5%에서 완전 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        )
    }

    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> Optional[TechnicalIndicators]:
        """
        기술적 지표 계산
        
        Args:
            df: 가격 데이터 DataFrame (open, high, low, close, volume 컬럼 필요)
            
        Returns:
            TechnicalIndicators: 계산된 기술적 지표 객체
        """
        try:
            logger = setup_logger(__name__)
            
            # RSI 계산
            close_prices = df['close'].astype(float)
            delta = close_prices.diff()
            gain = delta.copy()
            gain[delta <= 0] = 0.0
            loss = -delta.copy()
            loss[delta >= 0] = 0.0
            
            gain_avg = gain.rolling(window=14).mean()
            loss_avg = loss.rolling(window=14).mean()
            
            rs = gain_avg / loss_avg
            rsi = 100 - (100 / (1 + rs))
            
            # MACD 계산
            exp1 = close_prices.ewm(span=12).mean()
            exp2 = close_prices.ewm(span=26).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=9).mean()
            
            # 볼린저 밴드 계산
            bb_middle = close_prices.rolling(window=20).mean()
            bb_std = close_prices.rolling(window=20).std()
            bb_upper = bb_middle + (bb_std * 2)
            bb_lower = bb_middle - (bb_std * 2)
            
            # ATR 계산
            high_prices = df['high'].astype(float)
            low_prices = df['low'].astype(float)
            
            high_low = high_prices - low_prices
            high_close = (high_prices - close_prices.shift()).abs()
            low_close = (low_prices - close_prices.shift()).abs()
            
            # DataFrame으로 변환하여 concat 사용
            ranges_df = pd.DataFrame({
                'high_low': high_low,
                'high_close': high_close,
                'low_close': low_close
            })
            true_range = ranges_df.max(axis=1)
            atr = true_range.rolling(window=14).mean()
            
            # 이동평균선 계산
            ma20 = close_prices.rolling(window=20).mean()
            ma60 = close_prices.rolling(window=60).mean()
            ma120 = close_prices.rolling(window=120).mean()
            
            # 모멘텀 지표 계산
            current_price = float(close_prices.iloc[-1])
            prev_price = float(close_prices.iloc[-2]) if len(close_prices) > 1 else current_price
            
            # 1. 이동평균선 돌파 여부
            ma20_breakout = current_price > float(ma20.iloc[-1]) and prev_price <= float(ma20.iloc[-2]) if len(ma20) > 1 else False
            ma60_breakout = current_price > float(ma60.iloc[-1]) and prev_price <= float(ma60.iloc[-2]) if len(ma60) > 1 else False
            
            # 2. 상대강도(RS) 계산 (최근 14일 대비 상승률)
            if len(close_prices) >= 14:
                recent_avg = close_prices.tail(14).mean()
                rs_ratio = (current_price / recent_avg - 1) * 100
            else:
                rs_ratio = 0.0
            
            # 3. 52주 신고가 대비 위치 (최근 252일 중 최고가 대비)
            lookback_days = min(252, len(close_prices))
            if lookback_days > 0:
                high_52w = close_prices.tail(lookback_days).max()
                high_52w_ratio = (current_price / high_52w) * 100
            else:
                high_52w_ratio = 0.0
            
            # 4. 단기 가격 모멘텀 (5일, 20일 수익률)
            if len(close_prices) >= 5:
                price_5d_ago = float(close_prices.iloc[-5])
                momentum_5d = ((current_price / price_5d_ago) - 1) * 100
            else:
                momentum_5d = 0.0
                
            if len(close_prices) >= 20:
                price_20d_ago = float(close_prices.iloc[-20])
                momentum_20d = ((current_price / price_20d_ago) - 1) * 100
            else:
                momentum_20d = 0.0
            
            return TechnicalIndicators(
                rsi=float(rsi.iloc[-1]),
                macd=float(macd.iloc[-1]),
                macd_signal=float(macd_signal.iloc[-1]),
                bb_upper=float(bb_upper.iloc[-1]),
                bb_middle=float(bb_middle.iloc[-1]),
                bb_lower=float(bb_lower.iloc[-1]),
                atr=float(atr.iloc[-1]),
                ma20=float(ma20.iloc[-1]),
                ma60=float(ma60.iloc[-1]),
                ma120=float(ma120.iloc[-1]),
                # 모멘텀 지표 추가
                ma20_breakout=ma20_breakout,
                ma60_breakout=ma60_breakout,
                relative_strength=rs_ratio,
                high_52w_ratio=high_52w_ratio,
                momentum_5d=momentum_5d,
                momentum_20d=momentum_20d
            )
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"기술적 지표 계산 실패: {e}")
            return None
    
    @staticmethod
    def calculate_technical_score(indicators: TechnicalIndicators, current_price: float) -> float:
        """
        기술적 분석 점수 계산 (완화된 조건)
        
        Args:
            indicators: 기술적 지표 객체
            current_price: 현재 가격
            
        Returns:
            float: 기술적 분석 점수 (0-10점)
        """
        score = 0.0
        
        try:
            # RSI 점수 (완화된 기준: 40/50/60)
            if indicators.rsi <= 40:
                score += 3.0
            elif indicators.rsi <= 50:
                score += 2.0
            elif indicators.rsi <= 60:
                score += 1.0
            
            # 볼린저 밴드 점수 (완화된 기준: 30%/60%)
            if indicators.bb_upper != indicators.bb_lower:  # 0으로 나누기 방지
                bb_position = (current_price - indicators.bb_lower) / (indicators.bb_upper - indicators.bb_lower)
                if bb_position <= 0.3:  # 30% 이내
                    score += 2.0
                elif bb_position <= 0.6:  # 60% 이내
                    score += 1.0
            
            # MACD 점수 (골든크로스 + 상승 모멘텀 고려)
            if indicators.macd > indicators.macd_signal:
                # 기본 골든크로스 점수
                score += 1.0
                # 상승 모멘텀 추가 점수 (MACD가 신호선보다 크게 위에 있을 때)
                macd_diff = indicators.macd - indicators.macd_signal
                if macd_diff > 0:  # 상승 모멘텀이 있을 때
                    score += 0.5
            
            # 이동평균선 점수 (완화된 기준: 5% 이내)
            if current_price > 0:  # 0으로 나누기 방지
                ma_distance = abs(current_price - indicators.ma20) / current_price
                if ma_distance <= 0.05:  # 5% 이내
                    score += 1.0
                    # 20일선 위에 있으면 추가 점수
                    if current_price > indicators.ma20:
                        score += 0.5
            
            # 🚀 모멘텀 지표 점수 추가
            # 1. 이동평균선 돌파 점수
            if indicators.ma20_breakout:
                score += 1.0  # 20일선 돌파
            if indicators.ma60_breakout:
                score += 1.5  # 60일선 돌파 (더 중요한 신호)
            
            # 2. 상대강도(RS) 점수
            if indicators.relative_strength > 2.0:  # 14일 평균 대비 2% 이상 상승
                score += 1.0
            elif indicators.relative_strength > 0.0:  # 양수 상승
                score += 0.5
            
            # 3. 52주 신고가 대비 위치 점수 (적정 범위: 70-95%)
            if 70.0 <= indicators.high_52w_ratio <= 95.0:
                score += 1.0  # 적정 범위
            elif indicators.high_52w_ratio > 95.0:
                score += 0.5  # 신고가 근처 (모멘텀 있음)
            
            # 4. 단기 모멘텀 점수
            if indicators.momentum_5d > 3.0:  # 5일 수익률 3% 이상
                score += 1.0
            elif indicators.momentum_5d > 0.0:  # 양수
                score += 0.5
                
            if indicators.momentum_20d > 5.0:  # 20일 수익률 5% 이상
                score += 1.0
            elif indicators.momentum_20d > 0.0:  # 양수
                score += 0.5
            
            return min(score, 10.0)  # 최대 10점
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"기술적 점수 계산 실패: {e}")
            return 0.0
    
    @staticmethod
    def get_market_cap_type(market_cap: float) -> MarketCapType:
        """
        시가총액 분류
        
        Args:
            market_cap: 시가총액 (단위: 억원)
            
        Returns:
            MarketCapType: 시가총액 분류
        """
        if market_cap >= TechnicalAnalyzer.LARGE_CAP_THRESHOLD:
            return MarketCapType.LARGE_CAP
        elif market_cap >= TechnicalAnalyzer.MID_CAP_THRESHOLD:
            return MarketCapType.MID_CAP
        else:
            return MarketCapType.SMALL_CAP
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        RSI 계산 (개별 사용 가능)
        
        Args:
            prices: 가격 시리즈
            period: 계산 기간
            
        Returns:
            pd.Series: RSI 값
        """
        try:
            # 가격 시리즈를 float로 변환
            prices = prices.astype(float)
            delta = prices.diff()
            
            # 상승분과 하락분 분리
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            
            # 이동평균 계산
            ma_up = up.rolling(window=period).mean()
            ma_down = down.rolling(window=period).mean()
            
            # RSI 계산
            rs = ma_up / ma_down
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.fillna(50)  # NaN값은 중립값으로 처리
            
        except Exception:
            # 계산 실패시 중립값 반환
            return pd.Series([50] * len(prices), index=prices.index)

    @staticmethod
    def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """
        MACD 계산 (개별 사용 가능)
        
        Args:
            prices: 가격 시리즈
            fast: 빠른 이동평균 기간
            slow: 느린 이동평균 기간
            signal: 신호선 기간
            
        Returns:
            dict: MACD, Signal, Histogram
        """
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=signal).mean()
        histogram = macd - macd_signal
        
        return {
            'macd': macd,
            'signal': macd_signal,
            'histogram': histogram
        }

    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
        """
        볼린저 밴드 계산 (개별 사용 가능)
        
        Args:
            prices: 가격 시리즈
            period: 이동평균 기간
            std_dev: 표준편차 배수
            
        Returns:
            dict: Upper, Middle, Lower 밴드
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        ATR (Average True Range) 계산 (개별 사용 가능)
        
        Args:
            high: 고가 시리즈
            low: 저가 시리즈
            close: 종가 시리즈
            period: 계산 기간
            
        Returns:
            pd.Series: ATR 값
        """
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        
        ranges_df = pd.DataFrame({
            'high_low': high_low,
            'high_close': high_close,
            'low_close': low_close
        })
        true_range = ranges_df.max(axis=1)
        return true_range.rolling(window=period).mean()

    @staticmethod
    def calculate_pattern_stop_loss(current_price: float,
                                  pattern_type: PatternType,
                                  candles: List[Dict[str, Any]],
                                  target_price: float) -> float:
        """
        패턴별 차별화된 손절매 계산 (개선된 손익비 전략 적용)
        
        Args:
            current_price: 현재가 (진입가)
            pattern_type: 패턴 타입
            candles: 캔들 데이터 리스트
            target_price: 목표가
            
        Returns:
            float: 손절매 가격
        """
        try:
            logger = setup_logger(__name__)
            
            # 패턴 설정 가져오기
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config:
                logger.warning(f"패턴 설정을 찾을 수 없음: {pattern_type}")
                return current_price * 0.95  # 기본값: 5% 손절
            
            # 🎯 개선된 손익비 기반 손절가 계산
            profit_potential = target_price - current_price
            
            # 패턴별 목표 손익비 적용
            if pattern_type == PatternType.MORNING_STAR:
                target_risk_reward_ratio = 2.5  # 1:2.5
            elif pattern_type == PatternType.THREE_WHITE_SOLDIERS:
                target_risk_reward_ratio = 3.0  # 1:3.0
            else:
                target_risk_reward_ratio = 2.0  # 1:2.0 (표준)
            
            # 손익비 기반 손절가 계산
            max_acceptable_loss = profit_potential / target_risk_reward_ratio
            ratio_based_stop_loss = current_price - max_acceptable_loss
            
            # 기존 패턴별 손절가 계산 (참고용)
            pattern_based_stop_loss = None
            
            if pattern_config.stop_loss_method == "entry_based":  # 진입가 기준 손절 (모든 패턴)
                # 패턴별 기술적 지지선 계산
                if pattern_type == PatternType.MORNING_STAR and len(candles) >= 3:
                    # 샛별: 두 번째 캔들 저가
                    pattern_based_stop_loss = candles[-2]['low_price'] * 0.98
                elif pattern_type == PatternType.BULLISH_ENGULFING and len(candles) >= 2:
                    # 상승장악형: 장악 캔들 저가
                    pattern_based_stop_loss = candles[-1]['low_price'] * 0.98
                elif pattern_type == PatternType.THREE_WHITE_SOLDIERS and len(candles) >= 3:
                    # 세 백병: 첫 번째 백병 저가
                    pattern_based_stop_loss = candles[-3]['low_price'] * 0.97
                elif pattern_type == PatternType.ABANDONED_BABY and len(candles) >= 3:
                    # 버려진 아기: 갭 메움 기준
                    gap_fill_price = candles[-2]['high_price']
                    pattern_based_stop_loss = min(gap_fill_price * 0.99, current_price * 0.96)
                elif pattern_type == PatternType.HAMMER and len(candles) >= 1:
                    # 망치형: 실체 하단
                    hammer_candle = candles[-1]
                    body_low = min(hammer_candle['open_price'], hammer_candle['close_price'])
                    pattern_based_stop_loss = body_low * 0.98
            
            # 🔄 이중 손절 시스템: 두 방식 중 더 높은 손절가 선택 (안전한 방향)
            if pattern_based_stop_loss is not None:
                final_stop_loss = max(ratio_based_stop_loss, pattern_based_stop_loss)
                loss_method = "이중시스템"
            else:
                final_stop_loss = ratio_based_stop_loss
                loss_method = "손익비기반"
            
            # 최대 손실률 제한 (안전장치)
            max_loss_stop = current_price * (1 - pattern_config.max_loss_ratio)
            final_stop_loss = max(final_stop_loss, max_loss_stop)
            
            # 손익비 검증
            actual_profit_potential = target_price - current_price
            actual_loss_potential = current_price - final_stop_loss
            actual_risk_reward_ratio = actual_profit_potential / actual_loss_potential if actual_loss_potential > 0 else 0
            
            logger.debug(f"개선된 손절매 계산 - {pattern_config.pattern_name}:")
            logger.debug(f"   진입가: {current_price:,.0f}원")
            logger.debug(f"   목표가: {target_price:,.0f}원 (+{(target_price/current_price-1)*100:.1f}%)")
            logger.debug(f"   손절가: {final_stop_loss:,.0f}원 ({(final_stop_loss/current_price-1)*100:.1f}%)")
            logger.debug(f"   목표 손익비: 1:{target_risk_reward_ratio:.1f}")
            logger.debug(f"   실제 손익비: 1:{actual_risk_reward_ratio:.1f}")
            logger.debug(f"   계산방식: {loss_method}")
            
            return round(final_stop_loss, 0)
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"패턴별 손절매 계산 실패: {e}")
            return current_price * 0.95  # 기본값: 5% 손절

    @staticmethod
    def calculate_stop_loss(current_price: float,
                          pattern_type: str,
                          candles: List[Dict[str, Any]],
                          target_price: float,
                          risk_reward_ratio: float = 3.0) -> float:
        """
        손익비를 고려한 손절매 계산
        
        Args:
            current_price: 현재가
            pattern_type: 패턴 유형 ('hammer' 또는 'bullish_engulfing')
            candles: 캔들 데이터 리스트
            target_price: 목표가
            risk_reward_ratio: 손익비 (기본 1:3)
            
        Returns:
            float: 손절매 가격
        """
        try:
            # 패턴 기반 기본 손절매
            if pattern_type == 'hammer':
                pattern_stop_loss = candles[-1]['low_price'] * 0.98
            else:  # bullish_engulfing
                pattern_stop_loss = min(candles[-2]['low_price'], candles[-1]['low_price']) * 0.98
            
            # 손익비 기반 손절매 계산
            profit_potential = target_price - current_price
            risk_tolerance = profit_potential / risk_reward_ratio
            ratio_based_stop_loss = current_price - risk_tolerance
            
            # 두 방식 중 더 보수적인 값 선택 (더 높은 손절가)
            final_stop_loss = max(pattern_stop_loss, ratio_based_stop_loss)
            
            # 현재가 대비 최대 손실 제한 (10%)
            max_loss_stop = current_price * 0.90
            final_stop_loss = max(final_stop_loss, max_loss_stop)
            
            return round(final_stop_loss, 0)
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"손절매 계산 실패: {e}")
            return current_price * 0.95  # 기본값: 5% 손절

    @staticmethod
    def calculate_pattern_target_price(current_price: float,
                                     pattern_type: PatternType,
                                     pattern_strength: float,
                                     market_cap_type: MarketCapType,
                                     market_condition: float = 1.0,
                                     volume_ratio: float = 1.0,
                                     rsi: float = 50.0,
                                     technical_score: float = 3.0) -> float:
        """
        패턴별 차별화된 목표가 계산 (개선된 버전 - 거래량, RSI, 기술점수 반영)
        
        Args:
            current_price: 현재가 (진입가)
            pattern_type: 패턴 타입
            pattern_strength: 패턴 강도
            market_cap_type: 시가총액 유형
            market_condition: 시장 상황
            volume_ratio: 거래량 증가율
            rsi: RSI 값
            technical_score: 기술점수
            
        Returns:
            float: 목표가 (개선된 계산)
        """
        try:
            logger = setup_logger(__name__)
            
            # 패턴 설정 가져오기
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config:
                logger.warning(f"패턴 설정을 찾을 수 없음: {pattern_type}")
                return TechnicalAnalyzer.calculate_target_price(
                    current_price, 0, pattern_strength, market_cap_type, market_condition
                )
            
            # 🎯 패턴별 기본 목표 수익률 설정 (PATTERN_CONFIGS와 일치)
            market_cap_key = market_cap_type.value
            target_returns = pattern_config.target_returns.get(market_cap_key, {
                "min": 0.02, "base": 0.03, "max": 0.04
            })
            
            # PATTERN_CONFIGS의 base 값을 기본으로 사용
            base_target_return = target_returns["base"]
            min_return = target_returns["min"]
            max_return = target_returns["max"]
            
            # 패턴 강도에 따른 기본 조정
            pattern_adjustment = (pattern_strength - 1.0) * 0.01  # 패턴 강도 1당 1%p 추가 (기존 2%p → 1%p로 보수적 조정)
            
            # 🔄 개선된 조정 로직 적용
            # 1. 거래량 증가율 반영
            volume_adjustment = 0.0
            if volume_ratio < 1.5:
                volume_adjustment = -0.005  # -0.5%p (유동성 부족)
            elif volume_ratio >= 1.5 and volume_ratio < 2.5:
                volume_adjustment = 0.0  # 기본값 유지
            elif volume_ratio >= 2.5 and volume_ratio < 4.0:
                volume_adjustment = 0.005  # +0.5%p (적정 관심도)
            else:  # 4.0배 이상
                volume_adjustment = 0.01  # +1%p (높은 관심도)
            
            # 2. RSI 상태 반영
            rsi_adjustment = 0.0
            if rsi <= 30:
                rsi_adjustment = 0.005  # +0.5%p (과매도 반등 기대)
            elif rsi > 30 and rsi <= 50:
                rsi_adjustment = 0.0  # 기본값 유지
            elif rsi > 50 and rsi <= 70:
                rsi_adjustment = -0.0025  # -0.25%p (상승 여력 제한)
            else:  # RSI > 70
                rsi_adjustment = -0.005  # -0.5%p (과매수 위험)
            
            # 3. 기술점수 반영
            technical_adjustment = 0.0
            if technical_score >= 5.0:
                technical_adjustment = 0.005  # +0.5%p (강한 기술적 지지)
            elif technical_score >= 3.0 and technical_score < 5.0:
                technical_adjustment = 0.0  # 기본값 유지
            else:  # technical_score < 3.0
                technical_adjustment = -0.005  # -0.5%p (기술적 약세)
            
            # 4. 시가총액별 민감도 조정
            sensitivity_multiplier = 1.0
            if market_cap_type == MarketCapType.LARGE_CAP:
                sensitivity_multiplier = 0.7  # 보수적
            elif market_cap_type == MarketCapType.MID_CAP:
                sensitivity_multiplier = 1.0  # 기본
            else:  # SMALL_CAP
                sensitivity_multiplier = 1.3  # 적극적
            
            # 조정값들에 민감도 적용
            volume_adjustment *= sensitivity_multiplier
            rsi_adjustment *= sensitivity_multiplier
            technical_adjustment *= sensitivity_multiplier
            
            # 최종 목표 수익률 계산
            final_target_return = base_target_return + pattern_adjustment + volume_adjustment + rsi_adjustment + technical_adjustment
            
            # 시장 상황 반영
            final_target_return *= market_condition
            
            # 최소/최대 제한 적용
            final_target_return = np.clip(final_target_return, min_return, max_return)
            
            # 최종 목표가 계산
            final_target = current_price * (1 + final_target_return)
            
            # 손익비 검증을 위한 예상 손절가 계산
            if pattern_type == PatternType.MORNING_STAR:
                target_risk_reward_ratio = 2.5
            elif pattern_type == PatternType.THREE_WHITE_SOLDIERS:
                target_risk_reward_ratio = 3.0
            else:
                target_risk_reward_ratio = 2.0
            
            estimated_stop_loss_ratio = final_target_return / target_risk_reward_ratio
            estimated_stop_loss = current_price * (1 - estimated_stop_loss_ratio)
            
            # 실제 손익비 계산
            profit_potential = final_target - current_price
            loss_potential = current_price - estimated_stop_loss
            actual_risk_reward_ratio = profit_potential / loss_potential if loss_potential > 0 else 0
            
            logger.debug(f"개선된 목표가 계산 - {pattern_config.pattern_name}:")
            logger.debug(f"   진입가: {current_price:,.0f}원")
            logger.debug(f"   기본 목표 수익률: {base_target_return:.1%}")
            logger.debug(f"   패턴 조정: {pattern_adjustment:+.1%}")
            logger.debug(f"   거래량 조정: {volume_adjustment:+.1%} (거래량: {volume_ratio:.1f}배)")
            logger.debug(f"   RSI 조정: {rsi_adjustment:+.1%} (RSI: {rsi:.1f})")
            logger.debug(f"   기술점수 조정: {technical_adjustment:+.1%} (점수: {technical_score:.1f})")
            logger.debug(f"   최종 목표 수익률: {final_target_return:.1%}")
            logger.debug(f"   최종 목표가: {final_target:,.0f}원")
            logger.debug(f"   목표 손익비: 1:{target_risk_reward_ratio:.1f}")
            logger.debug(f"   예상 손익비: 1:{actual_risk_reward_ratio:.1f}")
            
            return round(final_target, 0)
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"패턴별 목표가 계산 실패: {e}")
            return current_price * 1.02  # 기본값: 2% 목표

    @staticmethod
    def calculate_target_price(current_price: float,
                             atr: float,
                             pattern_strength: float,
                             market_cap_type: MarketCapType,
                             market_condition: float = 1.0,
                             min_risk_reward_ratio: float = 2.0) -> float:
        """
        현실적인 목표값 계산 (손익비 2:1 기준)
        
        Args:
            current_price: 현재가
            atr: Average True Range (참고용)
            pattern_strength: 패턴 강도
            market_cap_type: 시가총액 유형
            market_condition: 시장 상황
            min_risk_reward_ratio: 최소 손익비 (기본 2:1)
            
        Returns:
            float: 목표가
        """
        try:
            logger = setup_logger(__name__)
            
            base_return = TechnicalAnalyzer.TARGET_MULTIPLIERS[market_cap_type]["base"]
            min_return = TechnicalAnalyzer.TARGET_MULTIPLIERS[market_cap_type]["min"]
            max_return = TechnicalAnalyzer.TARGET_MULTIPLIERS[market_cap_type]["max"]
            
            # 패턴 강도에 따른 수익률 조정
            pattern_adjustment = (pattern_strength - 1.0) * 0.02  # 패턴 강도 1당 2%p 추가
            target_return = np.clip(
                base_return + pattern_adjustment,
                min_return,
                max_return
            )
            
            # 시장 상황 반영
            target_return *= market_condition
            
            # 기본 목표가 계산
            base_target = current_price * (1 + target_return)
            
            # 손익비 기반 최소 목표값 (예상 손실 4% 기준)
            estimated_risk = current_price * 0.04
            min_target_by_ratio = current_price + (estimated_risk * min_risk_reward_ratio)
            
            # 두 방식 중 더 높은 목표가 선택 (보수적 접근)
            final_target = max(base_target, min_target_by_ratio)
            
            logger.debug(f"목표가 계산 - 현재가: {current_price:,.0f}, "
                        f"시가총액: {market_cap_type.value}, "
                        f"패턴강도: {pattern_strength:.2f}, "
                        f"목표수익률: {target_return:.1%}, "
                        f"최종목표가: {final_target:,.0f}")
            
            return round(final_target, 0)
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"목표가 계산 실패: {e}")
            return current_price * 1.08  # 기본값: 8% 목표 

    @staticmethod
    def get_pattern_config(pattern_type: PatternType) -> Optional[PatternTradingConfig]:
        """
        패턴별 거래 설정 반환
        
        Args:
            pattern_type: 패턴 타입
            
        Returns:
            PatternTradingConfig: 패턴별 거래 설정
        """
        return TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
    
    @staticmethod
    def should_exit_by_time(pattern_type: PatternType, entry_date: datetime, current_date: datetime) -> Tuple[bool, str]:
        """
        시간 기반 종료 조건 확인
        
        Args:
            pattern_type: 패턴 타입
            entry_date: 진입일
            current_date: 현재일
            
        Returns:
            Tuple[bool, str]: (종료 여부, 종료 사유)
        """
        try:
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config or not pattern_config.time_based_exit:
                return False, ""
            
            holding_days = (current_date - entry_date).days
            
            # 최대 보유기간 초과
            if holding_days >= pattern_config.max_holding_days:
                return True, f"최대 보유기간({pattern_config.max_holding_days}일) 도달"
            
            return False, ""
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"시간 기반 종료 조건 확인 실패: {e}")
            return False, ""
    
    @staticmethod
    def should_partial_exit(pattern_type: PatternType, entry_date: datetime, current_date: datetime, 
                          current_profit_rate: float, position: 'Position') -> Tuple[bool, float, str]:
        """
        부분 익절 조건 확인 (누적 방식, 프로그램 재시작 대응)
        
        Args:
            pattern_type: 패턴 타입
            entry_date: 진입일
            current_date: 현재일
            current_profit_rate: 현재 수익률 (예: 0.1은 0.1%)
            position: 포지션 정보 (부분매도 상태 포함)
            
        Returns:
            Tuple[bool, float, str]: (부분 익절 여부, 익절 비율, 익절 사유)
        """
        try:
            logger = setup_logger(__name__)
            
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config:
                logger.debug(f"📊 패턴 설정을 찾을 수 없음: {pattern_type}")
                return False, 0.0, ""
            
            holding_days = (current_date - entry_date).days
            
            # 🔧 현재 부분매도 상태 확인
            current_stage = getattr(position, 'partial_exit_stage', 0)
            current_ratio = getattr(position, 'partial_exit_ratio', 0.0)
            
            # 🚨 중요: 수익률 변환 로직 완전 수정
            # position.profit_loss_rate는 이미 퍼센트 단위 (예: -0.72% → -0.72)
            # 이를 소수점 형태로 변환: -0.72% → -0.0072
            current_profit_rate_decimal = current_profit_rate / 100.0
            
            # 🔧 변환 과정 디버깅
            logger.debug(f"🔍 수익률 변환 과정:")
            logger.debug(f"   입력값 (퍼센트): {current_profit_rate}")
            logger.debug(f"   변환값 (소수): {current_profit_rate_decimal}")
            logger.debug(f"   검증: {current_profit_rate}% = {current_profit_rate_decimal:.4f} (소수)")
            
            logger.debug(f"🔍 부분 익절 조건 확인: {position.stock_name}")
            logger.debug(f"   패턴: {pattern_config.pattern_name}")
            logger.debug(f"   보유일수: {holding_days}일")
            logger.debug(f"   현재 수익률: {current_profit_rate:.3f}% (소수: {current_profit_rate_decimal:.5f})")
            logger.debug(f"   현재 단계: {current_stage}, 누적 비율: {current_ratio:.1%}")
            
            # 수익 실현 규칙을 순서대로 확인 (누적 방식)
            for i, rule in enumerate(pattern_config.profit_taking_rules):
                # 이미 완료된 단계는 건너뛰기 (current_stage는 완료된 단계 수)
                if i < current_stage:
                    logger.debug(f"   규칙 {i+1}: 이미 완료된 단계 건너뛰기")
                    continue
                
                min_profit_required = rule["min_profit"]  # 이미 소수점 형태 (0.015 = 1.5%)
                days_required = rule["days"]
                
                logger.debug(f"   규칙 {i+1} 확인:")
                logger.debug(f"     필요 일수: {days_required}일 (현재: {holding_days}일)")
                logger.debug(f"     필요 수익률: {min_profit_required:.4f} ({min_profit_required*100:.1f}%)")
                logger.debug(f"     현재 수익률: {current_profit_rate_decimal:.4f} ({current_profit_rate_decimal*100:.1f}%)")
                logger.debug(f"     비교: {current_profit_rate_decimal:.4f} >= {min_profit_required:.4f} ? {current_profit_rate_decimal >= min_profit_required}")
                
                # 🚨 핵심 수정: 조건 검증을 더 엄격하게 수행
                days_condition_met = holding_days >= days_required
                profit_condition_met = current_profit_rate_decimal >= min_profit_required
                
                logger.debug(f"     일수 조건: {'✅' if days_condition_met else '❌'} ({holding_days} >= {days_required})")
                logger.debug(f"     수익 조건: {'✅' if profit_condition_met else '❌'} ({current_profit_rate_decimal:.4f} >= {min_profit_required:.4f})")
                
                if days_condition_met and profit_condition_met:
                    # 현재 단계의 매도 비율 계산
                    target_ratio = rule["partial_exit"]
                    current_exit_ratio = target_ratio - current_ratio
                    
                    logger.debug(f"     목표 비율: {target_ratio:.1%}")
                    logger.debug(f"     매도할 비율: {current_exit_ratio:.1%}")
                    
                    if current_exit_ratio > 0:  # 아직 매도하지 않은 부분이 있으면
                        exit_reason = f"{rule['days']}일차 수익실현 규칙 (단계 {i+1}, 누적 {target_ratio:.0%})"
                        logger.info(f"✅ 부분 익절 조건 만족: {position.stock_name}")
                        logger.info(f"   조건: {days_required}일 이상 & {min_profit_required*100:.1f}% 이상")
                        logger.info(f"   실제: {holding_days}일 & {current_profit_rate:.3f}%")
                        logger.info(f"   매도: {current_exit_ratio:.1%} ({exit_reason})")
                        return True, current_exit_ratio, exit_reason
                    else:
                        logger.debug(f"     이미 매도 완료됨 (비율: {current_exit_ratio:.1%})")
                else:
                    logger.debug(f"     조건 미충족으로 다음 규칙 확인")
            
            logger.debug(f"❌ 부분 익절 조건 미충족: {position.stock_name}")
            return False, 0.0, ""
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"부분 익절 조건 확인 실패: {e}")
            return False, 0.0, ""
    
    @staticmethod
    def should_exit_by_momentum(pattern_type: PatternType, recent_candles: List[Dict[str, Any]], 
                              indicators: TechnicalIndicators) -> Tuple[bool, str]:
        """
        모멘텀 기반 종료 조건 확인
        
        Args:
            pattern_type: 패턴 타입
            recent_candles: 최근 캔들 데이터
            indicators: 기술적 지표
            
        Returns:
            Tuple[bool, str]: (종료 여부, 종료 사유)
        """
        try:
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config or not pattern_config.momentum_exit:
                return False, ""
            
            if len(recent_candles) < 3:
                return False, ""
            
            # 연속 하락 확인 (2일로 단축)
            consecutive_decline = True
            for i in range(-2, -1):  # 기존 -3, -1 → -2, -1 (2일 연속 하락)
                if recent_candles[i]['close_price'] >= recent_candles[i-1]['close_price']:
                    consecutive_decline = False
                    break
            
            # RSI 과매수 확인 (더 엄격하게)
            rsi_overbought = indicators.rsi > 65  # 기존 70 → 65
            
            # MACD 데드크로스 확인
            macd_bearish = indicators.macd < indicators.macd_signal
            
            # 모멘텀 소실 조건
            momentum_exit_conditions = []
            if consecutive_decline:
                momentum_exit_conditions.append("연속 2일 하락")  # 기존 3일 → 2일
            if rsi_overbought:
                momentum_exit_conditions.append("RSI 과매수")
            if macd_bearish:
                momentum_exit_conditions.append("MACD 데드크로스")
            
            # 1개 이상 조건 충족시 모멘텀 소실 판단 (기존 2개 → 1개)
            if len(momentum_exit_conditions) >= 1:
                return True, f"모멘텀 소실: {', '.join(momentum_exit_conditions)}"
            
            return False, ""
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"모멘텀 기반 종료 조건 확인 실패: {e}")
            return False, ""
    
    @staticmethod
    def get_entry_timing_message(pattern_type: PatternType) -> str:
        """
        패턴별 진입 타이밍 메시지 반환
        
        Args:
            pattern_type: 패턴 타입
            
        Returns:
            str: 진입 타이밍 메시지
        """
        pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
        if not pattern_config:
            return "익일 시가 매수"
        
        timing_messages = {
            "immediate": "패턴 완성 즉시 매수",
            "next_day": "익일 시가 매수", 
            "confirmation": "추가 확인 후 매수"
        }
        
        base_message = timing_messages.get(pattern_config.entry_timing, "익일 시가 매수")
        
        if pattern_config.confirmation_required:
            base_message += " (상승 확인 필수)"
            
        return base_message 