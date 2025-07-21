"""
캔들패턴 감지 도구 클래스

다양한 캔들패턴 감지 기능을 정적 메서드로 제공하는 클래스입니다.
"""
from typing import List, Tuple
from dataclasses import dataclass

from core.enums import PatternType
from utils.logger import setup_logger


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
        샛별 패턴 감지 (강화된 조건 - 더 엄격한 기준)
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
            
            # 🔧 강화된 기본 조건 검사
            if not first_candle.is_bearish or not last_candle.is_bullish:
                return False, 0.0
            
            # 🔧 강화된 조건 1: 첫 번째 캔들의 실체 크기가 충분해야 함
            price_range = first_candle.high_price - first_candle.low_price
            if price_range == 0 or first_candle.body_size < price_range * 0.6:  # 실체가 전체 범위의 60% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 2: 가운데 캔들은 첫 번째 캔들보다 현저히 작아야 함
            if middle_candle.body_size >= first_candle.body_size * 0.5:  # 기존: 단순 비교 → 개선: 50% 이하
                return False, 0.0
            
            # 🔧 강화된 조건 3: 가운데 캔들의 위치 검증 (갭다운 확인)
            if middle_candle.high_price > first_candle.close_price:  # 갭다운이 없으면 약한 패턴
                return False, 0.0
            
            # 🔧 강화된 조건 4: 마지막 캔들의 강력한 상승 확인
            first_midpoint = (first_candle.open_price + first_candle.close_price) / 2
            
            # 기본 조건: 마지막 캔들이 첫 번째 캔들의 중점 이상까지 상승
            basic_condition = (
                last_candle.close_price > first_midpoint and
                middle_candle.low_price < first_candle.close_price and
                middle_candle.low_price < last_candle.open_price
            )
            
            if not basic_condition:
                return False, 0.0
            
            # 🔧 강화된 조건 5: 마지막 캔들의 갭업 확인
            if last_candle.open_price <= middle_candle.high_price:  # 갭업이 없으면 약한 패턴
                return False, 0.0
            
            # 🔧 강화된 조건 6: 마지막 캔들의 실체 크기 검증
            if last_candle.body_size < first_candle.body_size * 0.4:  # 충분한 상승력 필요
                return False, 0.0
            
            # 🔧 강화된 조건 7: 마지막 캔들의 위꼬리 길이 제한
            if last_candle.upper_shadow > last_candle.body_size * 0.5:  # 위꼬리가 너무 길면 약한 패턴
                return False, 0.0
            
            # 🔧 개선된 패턴 강도 계산
            # 1. 침투 강도 (마지막 캔들이 첫 번째 캔들을 얼마나 회복했는가)
            total_decline = first_candle.open_price - first_candle.close_price
            recovery_amount = last_candle.close_price - first_candle.close_price
            recovery_ratio = recovery_amount / total_decline if total_decline > 0 else 0
            
            # 2. 갭 강도 (갭다운과 갭업의 크기)
            gap_down_size = first_candle.close_price - middle_candle.high_price
            gap_up_size = last_candle.open_price - middle_candle.high_price
            avg_gap_size = (gap_down_size + gap_up_size) / 2
            gap_ratio = avg_gap_size / first_candle.close_price if first_candle.close_price > 0 else 0
            
            # 3. 실체 비율 (마지막 캔들의 실체가 첫 번째 캔들 대비 얼마나 큰가)
            body_ratio = last_candle.body_size / first_candle.body_size
            
            # 4. 최종 패턴 강도 계산 (1.0-3.0 범위)
            strength = (
                recovery_ratio * 1.0 +     # 회복력 (최대 1.0)
                gap_ratio * 50.0 +         # 갭 강도 (최대 1.0 추정)
                min(body_ratio, 1.0) * 1.0 # 실체 비율 (최대 1.0)
            )
            
            # 강도 범위 제한 및 최소값 보장
            final_strength = max(1.5, min(strength, 3.0))  # 샛별은 최소 1.5 강도 (기존 2.0에서 완화)
            
            return True, final_strength
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"샛별 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_three_white_soldiers_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        세 백병 패턴 감지 (강화된 조건 - 더 엄격한 기준)
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
            
            # 🔧 강화된 기본 조건: 모든 캔들이 양봉이어야 함
            if not (first_candle.is_bullish and second_candle.is_bullish and third_candle.is_bullish):
                return False, 0.0
            
            # 🔧 강화된 조건 1: 연속 상승 확인 (각 캔들의 시가도 고려)
            if not (first_candle.close_price < second_candle.close_price < third_candle.close_price):
                return False, 0.0
            
            # 🔧 강화된 조건 2: 각 캔들의 시가가 이전 캔들 실체 안에서 열려야 함 (갭업 제한)
            if (second_candle.open_price > first_candle.close_price or 
                second_candle.open_price < first_candle.close_price * 0.995):  # 0.5% 이하 갭만 허용
                return False, 0.0
            
            if (third_candle.open_price > second_candle.close_price or 
                third_candle.open_price < second_candle.close_price * 0.995):  # 0.5% 이하 갭만 허용
                return False, 0.0
            
            # 🔧 강화된 조건 3: 각 캔들의 실체 크기가 충분해야 함
            avg_body_size = (first_candle.body_size + second_candle.body_size + third_candle.body_size) / 3
            price_range = third_candle.high_price - first_candle.low_price
            
            if price_range == 0 or avg_body_size < price_range * 0.6:  # 실체가 전체 범위의 60% 이상 (기존 50% → 60%)
                return False, 0.0
            
            # 🔧 강화된 조건 4: 위꼬리 길이 제한 (더 엄격)
            for candle in [first_candle, second_candle, third_candle]:
                if candle.upper_shadow > candle.body_size * 0.3:  # 위꼬리가 실체의 30% 이하 (기존 100% → 30%)
                    return False, 0.0
            
            # 🔧 강화된 조건 5: 아래꼬리 길이 제한 (너무 긴 아래꼬리는 불안정)
            for candle in [first_candle, second_candle, third_candle]:
                if candle.lower_shadow > candle.body_size * 0.5:  # 아래꼬리가 실체의 50% 이하
                    return False, 0.0
            
            # 🔧 강화된 조건 6: 연속성 검증 (각 캔들의 상승폭이 일정 수준 이상)
            min_individual_gain = 0.01  # 각 캔들마다 최소 1% 상승
            for candle in [first_candle, second_candle, third_candle]:
                if (candle.close_price - candle.open_price) / candle.open_price < min_individual_gain:
                    return False, 0.0
            
            # 🔧 강화된 조건 7: 전체 상승폭 검증
            total_gain_ratio = (third_candle.close_price - first_candle.open_price) / first_candle.open_price
            if total_gain_ratio < 0.03:  # 전체 최소 3% 상승
                return False, 0.0
            
            # 🔧 개선된 패턴 강도 계산
            # 1. 연속성 강도 (각 캔들의 균등한 상승)
            gains = [
                (second_candle.close_price - first_candle.close_price) / first_candle.close_price,
                (third_candle.close_price - second_candle.close_price) / second_candle.close_price
            ]
            gain_consistency = 1.0 - abs(gains[0] - gains[1]) / max(gains[0], gains[1])  # 균등할수록 1에 가까움
            
            # 2. 실체 크기 일관성
            body_sizes = [first_candle.body_size, second_candle.body_size, third_candle.body_size]
            avg_body = sum(body_sizes) / 3
            body_consistency = 1.0 - (max(body_sizes) - min(body_sizes)) / avg_body
            
            # 3. 전체 상승 강도
            total_strength = min(total_gain_ratio * 20, 2.0)  # 최대 2.0
            
            # 4. 최종 패턴 강도 계산 (1.0-3.0 범위)
            final_strength = (
                gain_consistency * 1.0 +      # 연속성 (최대 1.0)
                body_consistency * 1.0 +      # 일관성 (최대 1.0)
                total_strength * 0.5          # 상승 강도 (최대 1.0)
            )
            
            # 강도 범위 제한 및 최소값 보장
            final_strength = max(1.2, min(final_strength, 3.0))  # 세 백병은 최소 1.2 강도 (기존 2.0에서 완화)
            
            return True, final_strength
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"세 백병 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_abandoned_baby_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        버려진 아기 패턴 감지 (강화된 조건 - 더 엄격한 기준)
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
            
            # 🔧 강화된 기본 조건: 첫 캔들은 음봉, 마지막 캔들은 양봉
            if not first_candle.is_bearish or not last_candle.is_bullish:
                return False, 0.0
            
            # 🔧 강화된 조건 1: 첫 번째 캔들의 실체 크기가 충분해야 함
            price_range = first_candle.high_price - first_candle.low_price
            if price_range == 0 or first_candle.body_size < price_range * 0.6:  # 실체가 전체 범위의 60% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 2: 가운데 캔들은 엄격한 도지여야 함
            if not middle_candle.is_doji:
                return False, 0.0
            
            # 도지의 추가 조건: 실체 크기가 매우 작아야 함
            middle_price_range = middle_candle.high_price - middle_candle.low_price
            if middle_price_range == 0 or middle_candle.body_size > middle_price_range * 0.05:  # 실체가 전체 범위의 5% 이하
                return False, 0.0
            
            # 🔧 강화된 조건 3: 명확한 갭다운과 갭업이 있어야 함
            has_gap_down = middle_candle.has_gap_down(first_candle)
            has_gap_up = last_candle.has_gap_up(middle_candle)
            
            if not (has_gap_down and has_gap_up):
                return False, 0.0
            
            # 🔧 강화된 조건 4: 갭의 크기가 충분해야 함
            gap_down_size = first_candle.low_price - middle_candle.high_price
            gap_up_size = last_candle.low_price - middle_candle.high_price
            
            # 갭 크기가 각각 최소 0.5% 이상이어야 함
            min_gap_ratio = 0.005
            if (gap_down_size / first_candle.close_price < min_gap_ratio or 
                gap_up_size / middle_candle.close_price < min_gap_ratio):
                return False, 0.0
            
            # 🔧 강화된 조건 5: 마지막 캔들의 강력한 상승 확인
            if last_candle.body_size < first_candle.body_size * 0.5:  # 마지막 캔들이 첫 캔들의 50% 이상 크기
                return False, 0.0
            
            # 🔧 강화된 조건 6: 마지막 캔들의 위꼬리 길이 제한
            if last_candle.upper_shadow > last_candle.body_size * 0.3:  # 위꼬리가 실체의 30% 이하
                return False, 0.0
            
            # 🔧 강화된 조건 7: 전체 회복력 검증
            total_decline = first_candle.open_price - first_candle.close_price
            total_recovery = last_candle.close_price - first_candle.close_price
            recovery_ratio = total_recovery / total_decline if total_decline > 0 else 0
            
            if recovery_ratio < 0.5:  # 최소 50% 회복
                return False, 0.0
            
            # 🔧 개선된 패턴 강도 계산
            # 1. 갭 강도 (갭다운과 갭업의 크기)
            avg_gap_size = (gap_down_size + gap_up_size) / 2
            gap_strength = min(avg_gap_size / first_candle.close_price * 100, 2.0)  # 최대 2.0
            
            # 2. 회복 강도 (첫 캔들 하락 대비 마지막 캔들 회복)
            recovery_strength = min(recovery_ratio * 2.0, 2.0)  # 최대 2.0
            
            # 3. 도지 품질 (도지가 완벽할수록 높은 점수)
            doji_quality = 1.0 - (middle_candle.body_size / middle_price_range) if middle_price_range > 0 else 0
            doji_strength = doji_quality * 1.0  # 최대 1.0
            
            # 4. 실체 크기 비율
            body_ratio_strength = min(last_candle.body_size / first_candle.body_size, 2.0)  # 최대 2.0
            
            # 5. 최종 패턴 강도 계산 (1.0-3.0 범위)
            final_strength = (
                gap_strength * 0.3 +         # 갭 강도 (최대 0.6)
                recovery_strength * 0.4 +    # 회복 강도 (최대 0.8)
                doji_strength * 0.2 +        # 도지 품질 (최대 0.2)
                body_ratio_strength * 0.3    # 실체 비율 (최대 0.6)
            ) + 1.0  # 기본 1.0점 + 추가 점수
            
            # 강도 범위 제한 및 최소값 보장
            final_strength = max(1.8, min(final_strength, 3.0))  # 버려진 아기는 최소 1.8 강도 (기존 2.5에서 완화)
            
            return True, final_strength
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"버려진 아기 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_hammer_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        망치형 패턴 감지 (강화된 조건 - 더 엄격한 기준)
        구조: 하락 추세 끝, 긴 아래꼬리
        
        Args:
            candles: 캔들 데이터 리스트
            
        Returns:
            Tuple[bool, float]: (패턴 발견 여부, 패턴 강도)
        """
        try:
            if len(candles) < 2:  # 하락 추세 확인을 위해 최소 2개 캔들 필요
                return False, 0.0
            
            current = candles[-1]
            previous = candles[-2] if len(candles) >= 2 else None
            
            # 🔧 강화된 조건 1: 기본 망치형 조건 (양봉만 허용)
            if current.is_bearish:
                return False, 0.0
            
            # 🔧 강화된 조건 2: 실체 크기 검증
            if current.body_size == 0:
                return False, 0.0
            
            # 전체 캔들 범위 대비 실체 크기 검증
            price_range = current.high_price - current.low_price
            if price_range == 0 or current.body_size < price_range * 0.2:  # 실체가 전체 범위의 20% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 3: 아래꼬리와 실체 비율 검증 (더 엄격)
            lower_shadow_ratio = current.lower_shadow / current.body_size
            upper_shadow_ratio = current.upper_shadow / current.body_size
            
            # 망치형 기본 조건 강화
            if not (lower_shadow_ratio >= PatternDetector.MIN_HAMMER_RATIO and  # 최소 1.8배
                    upper_shadow_ratio <= 0.3 and                              # 위꼬리 30% 이하 (기존 50% → 30%)
                    current.lower_shadow > 0 and
                    current.lower_shadow >= current.upper_shadow * 3):         # 아래꼬리가 위꼬리의 3배 이상 (기존 2배 → 3배)
                return False, 0.0
            
            # 🔧 강화된 조건 4: 하락 추세 확인 (이전 캔들과의 관계)
            if previous:
                # 이전 캔들이 하락 캔들이거나, 현재 캔들의 시가가 이전 캔들보다 낮아야 함
                downtrend_confirmed = (
                    previous.is_bearish or 
                    current.open_price < previous.close_price * 0.98  # 2% 이상 갭다운
                )
                
                if not downtrend_confirmed:
                    return False, 0.0
            
            # 🔧 강화된 조건 5: 아래꼬리의 절대적 길이 검증
            # 아래꼬리가 현재가의 일정 비율 이상이어야 함
            if current.lower_shadow / current.close_price < 0.01:  # 현재가의 1% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 6: 망치형의 위치 검증 (하락 후 반등)
            if current.close_price <= current.low_price + (price_range * 0.7):  # 하단 30% 이내에서 마감하면 약한 패턴
                return False, 0.0
            
            # 🔧 개선된 패턴 강도 계산
            # 1. 아래꼬리 비율 강도
            shadow_strength = min(lower_shadow_ratio / PatternDetector.MIN_HAMMER_RATIO, 2.0)  # 최대 2.0
            
            # 2. 실체 위치 강도 (위쪽에 위치할수록 강함)
            body_position = (current.close_price - current.low_price) / price_range if price_range > 0 else 0
            position_strength = body_position * 1.5  # 최대 1.5
            
            # 3. 하락 추세 강도 (이전 캔들과의 갭 크기)
            gap_strength = 0.0
            if previous:
                gap_ratio = abs(current.open_price - previous.close_price) / previous.close_price
                gap_strength = min(gap_ratio * 20, 1.0)  # 최대 1.0
            
            # 4. 위꼬리 페널티 (위꼬리가 길수록 감점)
            upper_shadow_penalty = upper_shadow_ratio * 0.5  # 페널티
            
            # 5. 최종 패턴 강도 계산 (1.0-3.0 범위)
            final_strength = (
                shadow_strength * 0.4 +      # 아래꼬리 강도 (최대 0.8)
                position_strength * 0.3 +    # 위치 강도 (최대 0.45)
                gap_strength * 0.2 +         # 갭 강도 (최대 0.2)
                0.5                          # 기본 점수
            ) - upper_shadow_penalty         # 위꼬리 페널티
            
            # 강도 범위 제한 및 최소값 보장
            final_strength = max(1.0, min(final_strength, 3.0))  # 망치형은 최소 1.0 강도
            
            return True, final_strength
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"망치형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def detect_bullish_engulfing_pattern(candles: List[CandleData]) -> Tuple[bool, float]:
        """
        상승장악형 패턴 감지 (강화된 조건 - 더 엄격한 기준)
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
            
            # 🔧 강화된 조건 1: 기본 조건 (첫 캔들 음봉, 두 번째 캔들 양봉)
            if not first_candle.is_bearish or not second_candle.is_bullish:
                return False, 0.0
            
            # 🔧 강화된 조건 2: 첫 번째 캔들의 실체 크기가 충분해야 함
            first_price_range = first_candle.high_price - first_candle.low_price
            if first_price_range == 0 or first_candle.body_size < first_price_range * 0.6:  # 실체가 전체 범위의 60% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 3: 완전한 장악 조건 (더 엄격)
            is_engulfing = (
                second_candle.open_price < first_candle.close_price and
                second_candle.close_price > first_candle.open_price and
                second_candle.low_price <= first_candle.low_price and      # 최저가도 장악
                second_candle.high_price >= first_candle.high_price        # 최고가도 장악
            )
            
            if not is_engulfing:
                return False, 0.0
            
            # 🔧 강화된 조건 4: 장악도 계산 및 최소 기준
            if first_candle.body_size == 0:
                return False, 0.0
            
            engulfing_ratio = second_candle.body_size / first_candle.body_size
            
            # 더 엄격한 장악도 기준
            if engulfing_ratio < PatternDetector.MIN_ENGULFING_RATIO * 1.5:  # 기존 1.05 → 1.575 (50% 증가)
                return False, 0.0
            
            # 🔧 강화된 조건 5: 두 번째 캔들의 품질 검증
            second_price_range = second_candle.high_price - second_candle.low_price
            if second_price_range == 0 or second_candle.body_size < second_price_range * 0.7:  # 실체가 전체 범위의 70% 이상
                return False, 0.0
            
            # 🔧 강화된 조건 6: 위꼬리 길이 제한
            if second_candle.upper_shadow > second_candle.body_size * 0.2:  # 위꼬리가 실체의 20% 이하
                return False, 0.0
            
            # 🔧 강화된 조건 7: 갭 조건 (갭다운 시작 선호)
            gap_condition = second_candle.open_price <= first_candle.low_price * 1.005  # 0.5% 이내 갭다운 허용
            
            # 🔧 강화된 조건 8: 상승 강도 검증
            price_gain_ratio = (second_candle.close_price - first_candle.open_price) / first_candle.open_price
            if price_gain_ratio < 0.01:  # 최소 1% 상승
                return False, 0.0
            
            # 🔧 개선된 패턴 강도 계산
            # 1. 장악 강도 (장악도 비율)
            engulf_strength = min(engulfing_ratio / PatternDetector.MIN_ENGULFING_RATIO, 3.0)  # 최대 3.0
            
            # 2. 완전성 강도 (얼마나 완전히 장악했는가)
            low_engulf = (first_candle.low_price - second_candle.low_price) / first_candle.close_price if first_candle.close_price > 0 else 0
            high_engulf = (second_candle.high_price - first_candle.high_price) / first_candle.close_price if first_candle.close_price > 0 else 0
            completeness = min((abs(low_engulf) + abs(high_engulf)) * 50, 2.0)  # 최대 2.0
            
            # 3. 실체 품질 강도
            body_quality_first = first_candle.body_size / first_price_range if first_price_range > 0 else 0
            body_quality_second = second_candle.body_size / second_price_range if second_price_range > 0 else 0
            body_quality = (body_quality_first + body_quality_second) * 1.0  # 최대 2.0
            
            # 4. 상승 강도
            price_strength = min(price_gain_ratio * 50, 2.0)  # 최대 2.0
            
            # 5. 갭 보너스
            gap_bonus = 0.3 if gap_condition else 0.0
            
            # 6. 최종 패턴 강도 계산 (1.0-3.0 범위)
            final_strength = (
                engulf_strength * 0.3 +      # 장악 강도 (최대 0.9)
                completeness * 0.2 +         # 완전성 (최대 0.4)
                body_quality * 0.2 +         # 실체 품질 (최대 0.4)
                price_strength * 0.2 +       # 상승 강도 (최대 0.4)
                gap_bonus                    # 갭 보너스 (최대 0.3)
            ) + 0.8  # 기본 0.8점
            
            # 강도 범위 제한 및 최소값 보장
            final_strength = max(1.2, min(final_strength, 3.0))  # 상승장악형은 최소 1.2 강도
            
            return True, final_strength
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"상승장악형 패턴 감지 실패: {e}")
            return False, 0.0
    
    @staticmethod
    def get_pattern_confidence(pattern_type: PatternType, pattern_strength: float, 
                             volume_ratio: float, technical_score: float) -> float:
        """
        패턴 신뢰도 계산 (개선된 버전 - 현실적인 신뢰도 분포)
        
        Args:
            pattern_type: 패턴 타입
            pattern_strength: 패턴 강도 (1.0-3.0)
            volume_ratio: 거래량 비율 (1.0-5.0)
            technical_score: 기술적 점수 (0-10)
            
        Returns:
            float: 신뢰도 (65-95%, 100%는 매우 예외적)
        """
        try:
            # 🔧 개선된 패턴별 기본 신뢰도 (더 보수적)
            pattern_base_confidence = {
                PatternType.MORNING_STAR: 82.0,        # 샛별 (기존 95% → 82%)
                PatternType.BULLISH_ENGULFING: 78.0,   # 상승장악형 (기존 90% → 78%)
                PatternType.ABANDONED_BABY: 80.0,      # 버려진 아기 (기존 90% → 80%)
                PatternType.THREE_WHITE_SOLDIERS: 75.0, # 세 백병 (기존 85% → 75%)
                PatternType.HAMMER: 68.0               # 망치형 (기존 75% → 68%)
            }
            
            # 🔧 개선된 가중치 (더 보수적)
            pattern_weights = {
                PatternType.MORNING_STAR: 0.25,        # 기존 0.45 → 0.25
                PatternType.BULLISH_ENGULFING: 0.22,   # 기존 0.40 → 0.22
                PatternType.ABANDONED_BABY: 0.23,      # 기존 0.40 → 0.23
                PatternType.THREE_WHITE_SOLDIERS: 0.20, # 기존 0.35 → 0.20
                PatternType.HAMMER: 0.18               # 기존 0.30 → 0.18
            }
            
            base_confidence = pattern_base_confidence.get(pattern_type, 65.0)
            pattern_weight = pattern_weights.get(pattern_type, 0.15)
            
            # 🔧 개선된 신뢰도 계산 로직
            # 1. 패턴 강도 기여분 (최대 +8%)
            pattern_contribution = min(pattern_strength * pattern_weight * 8, 8.0)
            
            # 2. 거래량 기여분 (최대 +5%)
            # 거래량 1.5배 이상일 때부터 점수 부여, 3배 이상에서 최대
            if volume_ratio >= 1.5:
                volume_contribution = min((volume_ratio - 1.5) / 1.5 * 5.0, 5.0)
            else:
                volume_contribution = 0.0
            
            # 3. 기술적 점수 기여분 (최대 +5%)
            # 기술점수 3점 이상일 때부터 점수 부여, 7점 이상에서 최대
            if technical_score >= 3.0:
                technical_contribution = min((technical_score - 3.0) / 4.0 * 5.0, 5.0)
            else:
                technical_contribution = 0.0
            
            # 4. 최종 신뢰도 계산
            final_confidence = base_confidence + pattern_contribution + volume_contribution + technical_contribution
            
            # 5. 현실적인 범위로 제한 (65-95%)
            final_confidence = max(65.0, min(final_confidence, 95.0))
            
            return round(final_confidence, 1)
            
        except Exception as e:
            logger = setup_logger(__name__)
            logger.error(f"패턴 신뢰도 계산 실패: {e}")
            return 65.0 