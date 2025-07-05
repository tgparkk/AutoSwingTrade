"""
캔들패턴 감지 도구 클래스

다양한 캔들패턴 감지 기능을 정적 메서드로 제공하는 클래스입니다.
"""
from typing import List, Tuple
from enum import Enum
from dataclasses import dataclass

from utils.logger import setup_logger


class PatternType(Enum):
    """캔들패턴 타입"""
    HAMMER = "hammer"  # 망치형
    BULLISH_ENGULFING = "bullish_engulfing"  # 상승장악형


@dataclass
class CandleData:
    """캔들 데이터 클래스"""
    date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    
    @property
    def body_size(self) -> float:
        """실체 크기"""
        return abs(self.close_price - self.open_price)
    
    @property
    def upper_shadow(self) -> float:
        """위꼬리 길이"""
        return self.high_price - max(self.open_price, self.close_price)
    
    @property
    def lower_shadow(self) -> float:
        """아래꼬리 길이"""
        return min(self.open_price, self.close_price) - self.low_price
    
    @property
    def is_bullish(self) -> bool:
        """상승 캔들 여부"""
        return self.close_price > self.open_price
    
    @property
    def is_bearish(self) -> bool:
        """하락 캔들 여부"""
        return self.close_price < self.open_price


class PatternDetector:
    """캔들패턴 감지 도구 클래스"""
    
    # 패턴 강도 계산 기준
    MIN_HAMMER_RATIO = 2.0  # 망치형 최소 비율
    MIN_ENGULFING_RATIO = 1.1  # 상승장악형 최소 비율
    
    @staticmethod
    def detect_hammer_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        망치형 패턴 감지
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 1:
                return False, 0.0
            
            current = candles[-1]
            
            # 망치형 조건 검사
            if current.is_bearish:  # 하락 캔들은 망치형이 아님
                return False, 0.0
            
            # 아래꼬리가 실체보다 최소 2배 이상 길어야 함
            if current.body_size == 0:
                return False, 0.0
            
            lower_shadow_ratio = current.lower_shadow / current.body_size
            upper_shadow_ratio = current.upper_shadow / current.body_size
            
            # 망치형 조건: 아래꼬리 길고, 위꼬리 짧음
            is_hammer = (
                lower_shadow_ratio >= PatternDetector.MIN_HAMMER_RATIO and
                upper_shadow_ratio <= 0.5 and
                current.lower_shadow > 0
            )
            
            if is_hammer:
                # 패턴 강도 계산
                strength = min(lower_shadow_ratio / PatternDetector.MIN_HAMMER_RATIO, 3.0)
                return True, strength
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"망치형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_bullish_engulfing_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        상승장악형 패턴 감지
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 2:
                return False, 0.0
            
            first_candle = candles[-2]  # 첫 번째 캔들 (하락)
            second_candle = candles[-1]  # 두 번째 캔들 (상승)
            
            # 상승장악형 조건 검사
            if not first_candle.is_bearish or not second_candle.is_bullish:
                return False, 0.0
            
            # 두 번째 캔들이 첫 번째 캔들을 완전히 감싸야 함
            is_engulfing = (
                second_candle.open_price < first_candle.close_price and
                second_candle.close_price > first_candle.open_price
            )
            
            if is_engulfing:
                # 장악도 계산
                if first_candle.body_size == 0:
                    return False, 0.0
                
                engulfing_ratio = second_candle.body_size / first_candle.body_size
                
                if engulfing_ratio >= PatternDetector.MIN_ENGULFING_RATIO:
                    # 패턴 강도 계산
                    strength = min(engulfing_ratio / PatternDetector.MIN_ENGULFING_RATIO, 3.0)
                    return True, strength
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"상승장악형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_doji_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        도지 패턴 감지 (추가 패턴)
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 1:
                return False, 0.0
            
            current = candles[-1]
            
            # 도지 조건: 시가와 종가가 거의 같음
            price_range = current.high_price - current.low_price
            if price_range == 0:
                return False, 0.0
            
            body_ratio = current.body_size / price_range
            
            # 실체가 전체 범위의 5% 이하인 경우 도지
            if body_ratio <= 0.05:
                strength = 1.0 - body_ratio * 20  # 실체가 작을수록 강도 증가
                return True, min(strength, 1.0)
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"도지 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_shooting_star_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        유성형 패턴 감지 (추가 패턴)
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 1:
                return False, 0.0
            
            current = candles[-1]
            
            # 유성형 조건 검사
            if current.body_size == 0:
                return False, 0.0
            
            upper_shadow_ratio = current.upper_shadow / current.body_size
            lower_shadow_ratio = current.lower_shadow / current.body_size
            
            # 유성형 조건: 위꼬리 길고, 아래꼬리 짧음
            is_shooting_star = (
                upper_shadow_ratio >= 2.0 and
                lower_shadow_ratio <= 0.5 and
                current.upper_shadow > 0
            )
            
            if is_shooting_star:
                # 패턴 강도 계산
                strength = min(upper_shadow_ratio / 2.0, 3.0)
                return True, strength
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"유성형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_piercing_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        관통형 패턴 감지 (추가 패턴)
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 2:
                return False, 0.0
            
            first_candle = candles[-2]  # 첫 번째 캔들 (하락)
            second_candle = candles[-1]  # 두 번째 캔들 (상승)
            
            # 관통형 조건 검사
            if not first_candle.is_bearish or not second_candle.is_bullish:
                return False, 0.0
            
            # 두 번째 캔들이 첫 번째 캔들의 중점 이상까지 관통
            first_midpoint = (first_candle.open_price + first_candle.close_price) / 2
            
            is_piercing = (
                second_candle.open_price < first_candle.close_price and
                second_candle.close_price > first_midpoint and
                second_candle.close_price < first_candle.open_price
            )
            
            if is_piercing:
                # 관통도 계산
                penetration_ratio = (second_candle.close_price - first_candle.close_price) / first_candle.body_size
                strength = min(penetration_ratio * 2, 2.0)
                return True, strength
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"관통형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def get_pattern_confidence(pattern_type: PatternType, pattern_strength: float, 
                             volume_ratio: float, technical_score: float) -> float:
        """
        패턴 신뢰도 계산
        
        Args:
            pattern_type: 패턴 타입
            pattern_strength: 패턴 강도
            volume_ratio: 거래량 비율
            technical_score: 기술적 점수
            
        Returns:
            float: 신뢰도 (0-100%)
        """
        try:
            # 패턴별 가중치
            pattern_weights = {
                PatternType.HAMMER: 0.35,
                PatternType.BULLISH_ENGULFING: 0.30
            }
            
            pattern_weight = pattern_weights.get(pattern_type, 0.25)
            
            # 신뢰도 계산
            confidence = min(
                (pattern_strength * pattern_weight + 
                 technical_score * 0.4 + 
                 min(volume_ratio, 3.0) * 0.25) / 3.0 * 100,
                100.0
            )
            
            return confidence
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"패턴 신뢰도 계산 실패: {e}")
            return 0.0 