"""
기술적 분석 도구 클래스

기술적 지표 계산과 분석 기능을 정적 메서드로 제공하는 클래스입니다.
"""
import pandas as pd
import numpy as np
from typing import Optional
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
        기술적 분석 점수 계산
        
        Args:
            indicators: 기술적 지표 객체
            current_price: 현재 가격
            
        Returns:
            float: 기술적 분석 점수 (0-10점)
        """
        score = 0.0
        
        try:
            # RSI 점수 (과매도 구간에서 높은 점수)
            if indicators.rsi <= 30:
                score += 3.0
            elif indicators.rsi <= 40:
                score += 2.0
            elif indicators.rsi <= 50:
                score += 1.0
            
            # 볼린저 밴드 점수 (하단선 근처에서 높은 점수)
            if indicators.bb_upper != indicators.bb_lower:  # 0으로 나누기 방지
                bb_position = (current_price - indicators.bb_lower) / (indicators.bb_upper - indicators.bb_lower)
                if bb_position <= 0.2:
                    score += 2.0
                elif bb_position <= 0.4:
                    score += 1.0
            
            # MACD 점수 (골든크로스 상황에서 높은 점수)
            if indicators.macd > indicators.macd_signal:
                score += 1.0
            
            # 이동평균선 점수 (지지선 근처에서 높은 점수)
            if current_price > 0:  # 0으로 나누기 방지
                ma_distance = abs(current_price - indicators.ma20) / current_price
                if ma_distance <= 0.02:  # 2% 이내
                    score += 1.0
            
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