"""
기술적 분석 도구 클래스

기술적 지표 계산과 분석 기능을 정적 메서드로 제공하는 클래스입니다.
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Any
from enum import Enum

from utils.logger import setup_logger
from core.enums import PatternType
from core.models import PatternTradingConfig


class MarketCapType(Enum):
    """시가총액 분류"""
    LARGE_CAP = "large_cap"  # 2조원 이상
    MID_CAP = "mid_cap"  # 3천억원 ~ 2조원
    SMALL_CAP = "small_cap"  # 3천억원 미만


class TechnicalIndicators:
    """기술적 지표 데이터"""
    def __init__(self, rsi: float, macd: float, macd_signal: float, 
                 bb_upper: float, bb_middle: float, bb_lower: float,
                 atr: float, ma20: float, ma60: float, ma120: float):
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
            min_holding_days=5,
            max_holding_days=10,
            optimal_holding_days=7,
            target_returns={
                "large_cap": {"min": 0.05, "base": 0.08, "max": 0.10},     # 개선된 목표 (손익비 2.5:1)
                "mid_cap": {"min": 0.06, "base": 0.08, "max": 0.12},       # 진입가 기준 3.2% 손절
                "small_cap": {"min": 0.07, "base": 0.08, "max": 0.14}      # 8% 목표 → 3.2% 손절 = 2.5:1
            },
            stop_loss_method="entry_based",  # 🔄 진입가 기준 손절 (개선됨)
            max_loss_ratio=0.032,            # 3.2% 최대 손실 (손익비 2.5:1 보장)
            trailing_stop=True,
            entry_timing="immediate",        # 패턴 완성 즉시
            confirmation_required=False,
            volume_multiplier=1.5,
            profit_taking_rules=[
                {"days": 3, "min_profit": 0.025, "partial_exit": 0.3},  # 3일차 2.5% 이상시 30% 익절
                {"days": 7, "min_profit": 0.04, "partial_exit": 0.5}    # 7일차 4% 이상시 50% 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.BULLISH_ENGULFING: PatternTradingConfig(
            pattern_type=PatternType.BULLISH_ENGULFING,
            pattern_name="상승장악형",
            base_confidence=90.0,
            min_holding_days=3,
            max_holding_days=7,
            optimal_holding_days=5,
            target_returns={
                "large_cap": {"min": 0.04, "base": 0.06, "max": 0.08},     # 개선된 목표 (손익비 2:1)
                "mid_cap": {"min": 0.05, "base": 0.06, "max": 0.09},       # 진입가 기준 3% 손절
                "small_cap": {"min": 0.06, "base": 0.06, "max": 0.10}      # 6% 목표 → 3% 손절 = 2:1
            },
            stop_loss_method="entry_based",  # 🔄 진입가 기준 손절 (개선됨)
            max_loss_ratio=0.03,             # 3% 최대 손실 (손익비 2:1 보장)
            trailing_stop=False,
            entry_timing="next_day",         # 장악 완성 후 익일
            confirmation_required=True,      # 익일 상승 확인 필요
            volume_multiplier=1.8,
            profit_taking_rules=[
                {"days": 2, "min_profit": 0.02, "partial_exit": 0.4},  # 2일차 2% 이상시 40% 익절
                {"days": 5, "min_profit": 0.03, "partial_exit": 0.6}   # 5일차 3% 이상시 60% 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.THREE_WHITE_SOLDIERS: PatternTradingConfig(
            pattern_type=PatternType.THREE_WHITE_SOLDIERS,
            pattern_name="세 백병",
            base_confidence=85.0,
            min_holding_days=7,
            max_holding_days=14,
            optimal_holding_days=10,
            target_returns={
                "large_cap": {"min": 0.06, "base": 0.09, "max": 0.12},     # 개선된 목표 (손익비 3:1)
                "mid_cap": {"min": 0.07, "base": 0.09, "max": 0.15},       # 진입가 기준 3% 손절
                "small_cap": {"min": 0.08, "base": 0.09, "max": 0.18}      # 9% 목표 → 3% 손절 = 3:1
            },
            stop_loss_method="entry_based",  # 🔄 진입가 기준 손절 (개선됨)
            max_loss_ratio=0.03,             # 3% 최대 손실 (손익비 3:1 보장)
            trailing_stop=True,
            entry_timing="confirmation",     # 세 번째 백병 확정 후
            confirmation_required=False,
            volume_multiplier=1.3,
            profit_taking_rules=[
                {"days": 4, "min_profit": 0.05, "partial_exit": 0.2},  # 4일차 5% 이상시 20% 익절
                {"days": 8, "min_profit": 0.08, "partial_exit": 0.4},  # 8일차 8% 이상시 40% 익절
                {"days": 12, "min_profit": 0.10, "partial_exit": 0.6}  # 12일차 10% 이상시 60% 익절
            ],
            time_based_exit=True,
            momentum_exit=False  # 추세 패턴이므로 모멘텀 기반 종료 비활성화
        ),
        
        PatternType.ABANDONED_BABY: PatternTradingConfig(
            pattern_type=PatternType.ABANDONED_BABY,
            pattern_name="버려진 아기",
            base_confidence=90.0,
            min_holding_days=5,
            max_holding_days=12,
            optimal_holding_days=8,
            target_returns={
                "large_cap": {"min": 0.06, "base": 0.08, "max": 0.10},     # 개선된 목표 (손익비 2:1)
                "mid_cap": {"min": 0.07, "base": 0.08, "max": 0.12},       # 진입가 기준 4% 손절
                "small_cap": {"min": 0.08, "base": 0.08, "max": 0.14}      # 8% 목표 → 4% 손절 = 2:1
            },
            stop_loss_method="entry_based",  # 🔄 진입가 기준 손절 (개선됨)
            max_loss_ratio=0.04,             # 4% 최대 손실 (손익비 2:1 보장)
            trailing_stop=True,
            entry_timing="immediate",        # 패턴 완성 즉시
            confirmation_required=False,
            volume_multiplier=2.0,           # 높은 거래량 요구
            profit_taking_rules=[
                {"days": 3, "min_profit": 0.04, "partial_exit": 0.3},  # 3일차 4% 이상시 30% 익절
                {"days": 6, "min_profit": 0.08, "partial_exit": 0.5},  # 6일차 8% 이상시 50% 익절
                {"days": 10, "min_profit": 0.12, "partial_exit": 0.7}  # 10일차 12% 이상시 70% 익절
            ],
            time_based_exit=True,
            momentum_exit=True
        ),
        
        PatternType.HAMMER: PatternTradingConfig(
            pattern_type=PatternType.HAMMER,
            pattern_name="망치형",
            base_confidence=75.0,
            min_holding_days=2,
            max_holding_days=5,
            optimal_holding_days=3,
            target_returns={
                "large_cap": {"min": 0.02, "base": 0.03, "max": 0.04},     # 개선된 목표 (손익비 2:1)
                "mid_cap": {"min": 0.02, "base": 0.03, "max": 0.05},       # 진입가 기준 1.5% 손절
                "small_cap": {"min": 0.03, "base": 0.03, "max": 0.06}      # 3% 목표 → 1.5% 손절 = 2:1
            },
            stop_loss_method="entry_based",  # 🔄 진입가 기준 손절 (개선됨)
            max_loss_ratio=0.015,            # 1.5% 최대 손실 (손익비 2:1 보장)
            trailing_stop=False,
            entry_timing="confirmation",     # 익일 상승 확인 후 진입
            confirmation_required=True,
            volume_multiplier=1.2,
            profit_taking_rules=[
                {"days": 1, "min_profit": 0.02, "partial_exit": 0.5},  # 1일차 2% 이상시 50% 익절
                {"days": 3, "min_profit": 0.03, "partial_exit": 0.8}   # 3일차 3% 이상시 80% 익절
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
                ma120=float(ma120.iloc[-1])
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
        # 가격 시리즈를 float로 변환
        prices = prices.astype(float)
        
        delta = prices.diff()
        # 타입 오류 수정: numpy를 사용하여 조건부 선택
        gain = delta.copy()
        gain[delta <= 0] = 0.0
        loss = -delta.copy()
        loss[delta >= 0] = 0.0
        
        gain_avg = gain.rolling(window=period).mean()
        loss_avg = loss.rolling(window=period).mean()
        
        rs = gain_avg / loss_avg
        return 100 - (100 / (1 + rs))
    
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
            
            if pattern_config.stop_loss_method == "pattern_low":  # 샛별: 두 번째 캔들 저가
                if len(candles) >= 3:
                    pattern_based_stop_loss = candles[-2]['low_price'] * 0.98
                    
            elif pattern_config.stop_loss_method == "engulfing_low":  # 상승장악형: 장악 캔들 저가
                if len(candles) >= 2:
                    pattern_based_stop_loss = candles[-1]['low_price'] * 0.98
                    
            elif pattern_config.stop_loss_method == "first_soldier_low":  # 세 백병: 첫 번째 백병 저가
                if len(candles) >= 3:
                    pattern_based_stop_loss = candles[-3]['low_price'] * 0.97
                    
            elif pattern_config.stop_loss_method == "gap_fill":  # 버려진 아기: 갭 메움 기준
                if len(candles) >= 3:
                    gap_fill_price = candles[-2]['high_price']
                    pattern_based_stop_loss = min(gap_fill_price * 0.99, current_price * 0.96)
                    
            elif pattern_config.stop_loss_method == "hammer_body_low":  # 망치형: 실체 하단
                if len(candles) >= 1:
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
            
            # 🎯 패턴별 기본 목표 수익률 설정
            if pattern_type == PatternType.MORNING_STAR:
                base_target_return = 0.08  # 8%
            elif pattern_type == PatternType.THREE_WHITE_SOLDIERS:
                base_target_return = 0.09  # 9%
            elif pattern_type == PatternType.BULLISH_ENGULFING:
                base_target_return = 0.06  # 6%
            elif pattern_type == PatternType.ABANDONED_BABY:
                base_target_return = 0.08  # 8%
            elif pattern_type == PatternType.HAMMER:
                base_target_return = 0.03  # 3%
            else:
                base_target_return = 0.05  # 기본값
            
            # 기존 패턴별 목표 수익률 계산 (참고용)
            market_cap_key = market_cap_type.value
            target_returns = pattern_config.target_returns.get(market_cap_key, {
                "min": 0.03, "base": 0.05, "max": 0.08
            })
            
            traditional_base_return = target_returns["base"]
            min_return = target_returns["min"]
            max_return = target_returns["max"]
            
            # 패턴 강도에 따른 기본 조정
            pattern_adjustment = (pattern_strength - 1.0) * 0.02  # 패턴 강도 1당 2%p 추가
            
            # 🔄 개선된 조정 로직 적용
            # 1. 거래량 증가율 반영
            volume_adjustment = 0.0
            if volume_ratio < 1.5:
                volume_adjustment = -0.01  # -1%p (유동성 부족)
            elif volume_ratio >= 1.5 and volume_ratio < 2.5:
                volume_adjustment = 0.0  # 기본값 유지
            elif volume_ratio >= 2.5 and volume_ratio < 4.0:
                volume_adjustment = 0.01  # +1%p (적정 관심도)
            else:  # 4.0배 이상
                volume_adjustment = 0.02  # +2%p (높은 관심도)
            
            # 2. RSI 상태 반영
            rsi_adjustment = 0.0
            if rsi <= 30:
                rsi_adjustment = 0.01  # +1%p (과매도 반등 기대)
            elif rsi > 30 and rsi <= 50:
                rsi_adjustment = 0.0  # 기본값 유지
            elif rsi > 50 and rsi <= 70:
                rsi_adjustment = -0.005  # -0.5%p (상승 여력 제한)
            else:  # RSI > 70
                rsi_adjustment = -0.01  # -1%p (과매수 위험)
            
            # 3. 기술점수 반영
            technical_adjustment = 0.0
            if technical_score >= 5.0:
                technical_adjustment = 0.01  # +1%p (강한 기술적 지지)
            elif technical_score >= 3.0 and technical_score < 5.0:
                technical_adjustment = 0.0  # 기본값 유지
            else:  # technical_score < 3.0
                technical_adjustment = -0.01  # -1%p (기술적 약세)
            
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
            return current_price * 1.08  # 기본값: 8% 목표

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
                          current_profit_rate: float) -> Tuple[bool, float, str]:
        """
        부분 익절 조건 확인
        
        Args:
            pattern_type: 패턴 타입
            entry_date: 진입일
            current_date: 현재일
            current_profit_rate: 현재 수익률
            
        Returns:
            Tuple[bool, float, str]: (부분 익절 여부, 익절 비율, 익절 사유)
        """
        try:
            pattern_config = TechnicalAnalyzer.PATTERN_CONFIGS.get(pattern_type)
            if not pattern_config:
                return False, 0.0, ""
            
            holding_days = (current_date - entry_date).days
            
            # 수익 실현 규칙 확인
            for rule in pattern_config.profit_taking_rules:
                if (holding_days >= rule["days"] and 
                    current_profit_rate >= rule["min_profit"]):
                    
                    return True, rule["partial_exit"], f"{rule['days']}일차 수익실현 규칙"
            
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
            
            # 연속 하락 확인
            consecutive_decline = True
            for i in range(-3, -1):
                if recent_candles[i]['close_price'] >= recent_candles[i-1]['close_price']:
                    consecutive_decline = False
                    break
            
            # RSI 과매수 확인
            rsi_overbought = indicators.rsi > 70
            
            # MACD 데드크로스 확인
            macd_bearish = indicators.macd < indicators.macd_signal
            
            # 모멘텀 소실 조건
            momentum_exit_conditions = []
            if consecutive_decline:
                momentum_exit_conditions.append("연속 3일 하락")
            if rsi_overbought:
                momentum_exit_conditions.append("RSI 과매수")
            if macd_bearish:
                momentum_exit_conditions.append("MACD 데드크로스")
            
            # 2개 이상 조건 충족시 모멘텀 소실 판단
            if len(momentum_exit_conditions) >= 2:
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