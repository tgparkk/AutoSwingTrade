"""
기술적 분석 도구 클래스

기술적 지표 계산과 분석 기능을 정적 메서드로 제공하는 클래스입니다.
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from enum import Enum

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
    
    # 목표값 계산 배수 (현실적인 수익률 기준)
    TARGET_MULTIPLIERS = {
        MarketCapType.LARGE_CAP: {"base": 0.05, "min": 0.03, "max": 0.08},      # 3-8%
        MarketCapType.MID_CAP: {"base": 0.08, "min": 0.05, "max": 0.12},       # 5-12%
        MarketCapType.SMALL_CAP: {"base": 0.10, "min": 0.07, "max": 0.15}      # 7-15%
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
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
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
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
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