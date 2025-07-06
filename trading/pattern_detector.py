"""
캔들패턴 감지 도구 클래스

다양한 캔들패턴 감지 기능을 정적 메서드로 제공하는 클래스입니다.
"""
from typing import List, Tuple
from enum import Enum
from dataclasses import dataclass

from utils.logger import setup_logger


class PatternType(Enum):
    """캔들패턴 타입 - 신뢰도 TOP 5"""
    MORNING_STAR = "morning_star"  # 샛별 (신뢰도 95%+)
    BULLISH_ENGULFING = "bullish_engulfing"  # 상승장악형 (신뢰도 90%+)
    THREE_WHITE_SOLDIERS = "three_white_soldiers"  # 세 백병 (신뢰도 85%+)
    ABANDONED_BABY = "abandoned_baby"  # 버려진 아기 (신뢰도 90%+)
    HAMMER = "hammer"  # 망치형 (신뢰도 75%+)


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
    
    @property
    def is_doji(self) -> bool:
        """도지 캔들 여부"""
        body_ratio = self.body_size / (self.high_price - self.low_price) if self.high_price != self.low_price else 0
        return body_ratio <= 0.10
    
    def has_gap_up(self, previous_candle: 'CandleData') -> bool:
        """상승 갭 여부"""
        return self.low_price > previous_candle.high_price
    
    def has_gap_down(self, previous_candle: 'CandleData') -> bool:
        """하락 갭 여부"""
        return self.high_price < previous_candle.low_price


class PatternDetector:
    """캔들패턴 감지 도구 클래스"""
    
    # 패턴 강도 계산 기준
    MIN_HAMMER_RATIO = 1.8  # 망치형 최소 비율
    MIN_ENGULFING_RATIO = 1.05  # 상승장악형 최소 비율
    MIN_BODY_SIZE_RATIO = 0.5  # 최소 실체 크기 비율
    
    @staticmethod
    def detect_morning_star_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        샛별 패턴 감지 (신뢰도 95%+)
        구조: 음봉 → 작은 캔들 → 양봉
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 3:
                return False, 0.0
            
            first_candle = candles[-3]   # 첫 번째 캔들 (하락)
            middle_candle = candles[-2]  # 가운데 캔들 (작은 캔들)
            last_candle = candles[-1]    # 마지막 캔들 (상승)
            
            # 샛별 조건 검사
            if not first_candle.is_bearish or not last_candle.is_bullish:
                return False, 0.0
            
            # 가운데 캔들은 첫 번째 캔들보다 작아야 함
            if middle_candle.body_size >= first_candle.body_size:
                return False, 0.0
            
            # 마지막 캔들이 첫 번째 캔들의 중점 이상까지 상승
            first_midpoint = (first_candle.open_price + first_candle.close_price) / 2
            
            is_morning_star = (
                last_candle.close_price > first_midpoint and
                middle_candle.low_price < first_candle.close_price and
                middle_candle.low_price < last_candle.open_price
            )
            
            if is_morning_star:
                # 패턴 강도 계산
                penetration_ratio = (last_candle.close_price - first_candle.close_price) / first_candle.body_size
                strength = min(penetration_ratio * 2.0, 3.0)
                return True, max(strength, 2.0)  # 샛별은 최소 2.0 강도
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"샛별 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_three_white_soldiers_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        세 백병 패턴 감지 (신뢰도 85%+)
        구조: 연속된 3개 상승 양봉
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 3:
                return False, 0.0
            
            first_candle = candles[-3]
            second_candle = candles[-2]
            third_candle = candles[-1]
            
            # 세 백병 조건 검사
            if not (first_candle.is_bullish and second_candle.is_bullish and third_candle.is_bullish):
                return False, 0.0
            
            # 연속 상승 확인
            if not (first_candle.close_price < second_candle.close_price < third_candle.close_price):
                return False, 0.0
            
            # 각 캔들의 실체 크기가 적절해야 함
            avg_body_size = (first_candle.body_size + second_candle.body_size + third_candle.body_size) / 3
            price_range = third_candle.high_price - first_candle.low_price
            
            # 실체 크기가 전체 범위의 일정 비율 이상
            if avg_body_size < price_range * PatternDetector.MIN_BODY_SIZE_RATIO:
                return False, 0.0
            
            # 위꼬리가 너무 길지 않아야 함
            if any(candle.upper_shadow > candle.body_size for candle in [first_candle, second_candle, third_candle]):
                return False, 0.0
            
            # 패턴 강도 계산
            total_gain = third_candle.close_price - first_candle.open_price
            strength = min(total_gain / first_candle.open_price * 100, 3.0)
            
            return True, max(strength, 2.0)  # 세 백병은 최소 2.0 강도
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"세 백병 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_abandoned_baby_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        버려진 아기 패턴 감지 (신뢰도 90%+)
        구조: 음봉 → 갭 도지 → 갭 양봉
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 3:
                return False, 0.0
            
            first_candle = candles[-3]   # 첫 번째 캔들 (하락)
            middle_candle = candles[-2]  # 가운데 캔들 (도지)
            last_candle = candles[-1]    # 마지막 캔들 (상승)
            
            # 버려진 아기 조건 검사
            if not first_candle.is_bearish or not last_candle.is_bullish:
                return False, 0.0
            
            # 가운데 캔들은 도지여야 함
            if not middle_candle.is_doji:
                return False, 0.0
            
            # 하락 갭과 상승 갭이 있어야 함
            has_gap_down = middle_candle.has_gap_down(first_candle)
            has_gap_up = last_candle.has_gap_up(middle_candle)
            
            if has_gap_down and has_gap_up:
                # 패턴 강도 계산 (갭 크기 고려)
                gap_down_size = first_candle.low_price - middle_candle.high_price
                gap_up_size = last_candle.low_price - middle_candle.high_price
                
                avg_gap_size = (gap_down_size + gap_up_size) / 2
                strength = min(avg_gap_size / middle_candle.close_price * 100, 3.0)
                
                return True, max(strength, 2.5)  # 버려진 아기는 최소 2.5 강도
            
            return False, 0.0
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"버려진 아기 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_hammer_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        망치형 패턴 감지 (신뢰도 75%+)
        구조: 하락 추세 끝, 긴 아래꼬리
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 1:
                return False, 0.0
            
            current = candles[-1]
            
            # 망치형 조건 검사 (상승 캔들만 허용)
            if current.is_bearish:
                return False, 0.0
            
            # 아래꼬리가 실체보다 최소 2배 이상 길어야 함
            if current.body_size == 0:
                return False, 0.0
            
            lower_shadow_ratio = current.lower_shadow / current.body_size
            upper_shadow_ratio = current.upper_shadow / current.body_size
            
            # 망치형 조건
            is_hammer = (
                lower_shadow_ratio >= PatternDetector.MIN_HAMMER_RATIO and
                upper_shadow_ratio <= 0.5 and
                current.lower_shadow > 0 and
                current.lower_shadow >= current.upper_shadow * 2
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
        상승장악형 패턴 감지 (신뢰도 90%+)
        구조: 음봉 → 큰 양봉이 완전히 감쌈
        
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
    def get_pattern_confidence(pattern_type: PatternType, pattern_strength: float, 
                             volume_ratio: float, technical_score: float) -> float:
        """
        패턴 신뢰도 계산 (TOP 5 패턴 기준)
        
        Args:
            pattern_type: 패턴 타입
            pattern_strength: 패턴 강도
            volume_ratio: 거래량 비율
            technical_score: 기술적 점수
            
        Returns:
            float: 신뢰도 (0-100%)
        """
        try:
            # 패턴별 기본 신뢰도와 가중치
            pattern_base_confidence = {
                PatternType.MORNING_STAR: 95.0,        # 샛별
                PatternType.BULLISH_ENGULFING: 90.0,   # 상승장악형
                PatternType.ABANDONED_BABY: 90.0,      # 버려진 아기
                PatternType.THREE_WHITE_SOLDIERS: 85.0, # 세 백병
                PatternType.HAMMER: 75.0               # 망치형
            }
            
            pattern_weights = {
                PatternType.MORNING_STAR: 0.45,        # 가장 높은 가중치
                PatternType.BULLISH_ENGULFING: 0.40,   
                PatternType.ABANDONED_BABY: 0.40,      
                PatternType.THREE_WHITE_SOLDIERS: 0.35, 
                PatternType.HAMMER: 0.30               # 가장 낮은 가중치
            }
            
            base_confidence = pattern_base_confidence.get(pattern_type, 70.0)
            pattern_weight = pattern_weights.get(pattern_type, 0.30)
            
            # 신뢰도 계산 (기본 신뢰도 + 추가 보정)
            additional_confidence = (
                pattern_strength * pattern_weight + 
                technical_score * 0.3 + 
                min(volume_ratio, 3.0) * 0.2
            ) / 3.0 * 30  # 최대 30% 추가 보정
            
            final_confidence = min(base_confidence + additional_confidence, 100.0)
            
            return final_confidence
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"패턴 신뢰도 계산 실패: {e}")
            return 0.0 