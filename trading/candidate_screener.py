"""
캔들패턴 기반 매수후보 종목 스크리너

망치형과 상승장악형 패턴을 감지하여 매수후보 종목을 선별하는 클래스입니다.
시가총액별 차별화된 목표값 설정과 기술적 지표 필터링을 지원합니다.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass

from api.kis_market_api import get_inquire_daily_itemchartprice
from api.kis_auth import KisAuth
from utils.logger import setup_logger
from utils.korean_time import now_kst
from trading.technical_analyzer import TechnicalAnalyzer, TechnicalIndicators, MarketCapType
from trading.pattern_detector import PatternDetector, PatternType, CandleData


@dataclass
class PatternResult:
    """패턴 감지 결과"""
    stock_code: str
    stock_name: str
    pattern_type: PatternType
    pattern_strength: float
    current_price: float
    target_price: float
    stop_loss: float
    market_cap_type: MarketCapType
    volume_ratio: float
    technical_score: float
    pattern_date: str
    confidence: float


class CandidateScreener:
    """캔들패턴 기반 매수후보 종목 스크리너"""
    
    def __init__(self, auth: KisAuth):
        self.auth = auth
        self.logger = setup_logger(__name__)
        
        # 목표값 계산 배수
        self.TARGET_MULTIPLIERS = {
            MarketCapType.LARGE_CAP: {"base": 1.5, "min": 0.8, "max": 1.2},
            MarketCapType.MID_CAP: {"base": 2.0, "min": 1.0, "max": 1.3},
            MarketCapType.SMALL_CAP: {"base": 2.5, "min": 1.2, "max": 1.5}
        }
        
        # 스크리닝 상태 관리
        self.last_screening_time: Optional[datetime] = None
        self.candidate_results: List[PatternResult] = []
    
    def run_candidate_screening(self, 
                               message_callback: Optional[Callable[[str], None]] = None,
                               force: bool = False) -> List[PatternResult]:
        """
        매수후보 종목 스크리닝 실행
        
        Args:
            message_callback: 메시지 전송 콜백 함수
            force: 강제 실행 여부
            
        Returns:
            List[PatternResult]: 후보 종목 리스트
        """
        try:
            current_time = now_kst()
            
            # 강제 실행이 아닌 경우 하루에 한 번만 스크리닝 실행
            if not force and (self.last_screening_time and 
                            current_time.date() == self.last_screening_time.date()):
                return self.candidate_results
            
            # 강제 실행이 아닌 경우 시간 체크 (장전 08:40~08:45)
            if not force:
                target_time = datetime.strptime("08:40", "%H:%M").time()
                current_time_only = current_time.time()
                
                # 08:40 ~ 08:45 사이에만 실행 (5분 윈도우)
                start_window = target_time
                end_window = datetime.strptime("08:45", "%H:%M").time()
                
                if not (start_window <= current_time_only <= end_window):
                    return self.candidate_results
            
            self.logger.info("🔍 장전 매수후보 종목 스크리닝 시작...")
            if message_callback:
                message_callback("🔍 장전 매수후보 종목 스크리닝을 시작합니다... (08:40)")
            
            # 캔들패턴 기반 후보 종목 스캔
            candidates = self.scan_candidates(limit=30)
            
            if candidates:
                self.candidate_results = candidates
                self.last_screening_time = current_time
                
                # 상위 10개 종목 메시지 전송
                if message_callback:
                    message = self.format_screening_results(candidates[:10])
                    message_callback(message)
                
                self.logger.info(f"✅ 스크리닝 완료: {len(candidates)}개 후보 종목 발견")
            else:
                self.logger.info("ℹ️ 조건에 맞는 후보 종목이 없습니다")
                if message_callback:
                    message_callback("ℹ️ 오늘은 조건에 맞는 후보 종목이 없습니다.")
            
            return candidates
                
        except Exception as e:
            self.logger.error(f"❌ 후보 종목 스크리닝 오류: {e}")
            if message_callback:
                message_callback(f"❌ 후보 종목 스크리닝 오류: {e}")
            return []
    
    def format_screening_results(self, candidates: List[PatternResult]) -> str:
        """스크리닝 결과 포맷팅"""
        if not candidates:
            return "조건에 맞는 후보 종목이 없습니다."
        
        message = f"🎯 매수후보 종목 TOP {len(candidates)}\n"
        message += "=" * 40 + "\n"
        
        for i, candidate in enumerate(candidates, 1):
            pattern_name = "🔨 망치형" if candidate.pattern_type.value == "hammer" else "📈 상승장악형"
            
            message += f"{i}. {candidate.stock_name} ({candidate.stock_code})\n"
            message += f"   패턴: {pattern_name}\n"
            message += f"   현재가: {candidate.current_price:,.0f}원\n"
            message += f"   목표가: {candidate.target_price:,.0f}원 "
            message += f"({(candidate.target_price/candidate.current_price-1)*100:.1f}%)\n"
            message += f"   신뢰도: {candidate.confidence:.1f}%\n"
            message += f"   거래량: {candidate.volume_ratio:.1f}배\n\n"
        
        message += "📊 투자 전략:\n"
        message += "• 패턴 완성 후 다음 봉에서 상승 확인 시 매수\n"
        message += "• 분할 매수 권장 (1차 50%, 2차 50%)\n"
        message += "• 손절매: 패턴 저점 하향 돌파 시"
        
        return message
    
    def get_candidate_results(self) -> List[PatternResult]:
        """현재 후보 종목 결과 반환"""
        return self.candidate_results.copy()
    
    def clear_candidate_results(self) -> None:
        """후보 종목 결과 초기화"""
        self.candidate_results = []
        self.last_screening_time = None
    
    def get_daily_price(self, stock_code: str, period: int = 120) -> Optional[pd.DataFrame]:
        """일봉 데이터 조회"""
        try:
            # 시작일과 종료일 계산
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period + 30)  # 여유분 추가
            
            # KIS API 호출
            df = get_inquire_daily_itemchartprice(
                output_dv="2",  # 차트 데이터
                div_code="J",   # 주식
                itm_no=stock_code,
                inqr_strt_dt=start_date.strftime("%Y%m%d"),
                inqr_end_dt=end_date.strftime("%Y%m%d"),
                period_code="D",  # 일봉
                adj_prc="1"      # 수정주가
            )
            
            if df is None or df.empty:
                return None
            
            # 컬럼명 표준화
            df = df.rename(columns={
                'stck_bsop_date': 'date',
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'stck_clpr': 'close',
                'acml_vol': 'volume'
            })
            
            # 데이터 타입 변환
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            # 날짜 순으로 정렬
            df = df.sort_values('date').reset_index(drop=True)
            
            # 필요한 기간만 반환
            return df.tail(period)
            
        except Exception as e:
            self.logger.error(f"일봉 데이터 조회 실패 {stock_code}: {e}")
            return None
    
    def load_stock_list(self, file_path: str = "stock_list.json") -> List[Dict]:
        """주식 리스트 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stocks = data.get('stocks', [])
            self.logger.info(f"총 {len(stocks)}개 종목 로드 완료")
            return stocks
            
        except Exception as e:
            self.logger.error(f"주식 리스트 로드 실패: {e}")
            return []
    

    

    

    
    def calculate_target_price(self, 
                             current_price: float, 
                             atr: float, 
                             pattern_strength: float,
                             market_cap_type: MarketCapType,
                             market_condition: float = 1.0) -> float:
        """동적 목표값 계산"""
        base_multiplier = self.TARGET_MULTIPLIERS[market_cap_type]["base"]
        min_multiplier = self.TARGET_MULTIPLIERS[market_cap_type]["min"]
        max_multiplier = self.TARGET_MULTIPLIERS[market_cap_type]["max"]
        
        # 종목 배수 (시가총액별)
        stock_multiplier = np.clip(
            min_multiplier + (pattern_strength - 1) * 0.2,
            min_multiplier,
            max_multiplier
        )
        
        # 최종 목표값 계산
        target_price = current_price + (atr * base_multiplier * stock_multiplier * market_condition)
        
        return round(target_price, 0)
    

    
    def scan_candidates(self, limit: int = 50) -> List[PatternResult]:
        """매수후보 종목 스캔"""
        stocks = self.load_stock_list()
        if not stocks:
            return []
        
        candidates = []
        processed_count = 0
        
        self.logger.info(f"총 {len(stocks)}개 종목 스캔 시작")
        
        for stock in stocks:
            try:
                stock_code = stock['code']
                stock_name = stock['name']
                
                # 일봉 데이터 조회 (최근 90일)
                df = self.get_daily_price(stock_code, period=90)
                if df is None or len(df) < 80:
                    continue
                
                # 캔들 데이터 변환
                candles = []
                for _, row in df.iterrows():
                    candle = CandleData(
                        date=row['date'],
                        open_price=row['open'],
                        high_price=row['high'],
                        low_price=row['low'],
                        close_price=row['close'],
                        volume=row['volume']
                    )
                    candles.append(candle)
                
                current_price = candles[-1].close_price
                
                # 기술적 지표 계산
                indicators = TechnicalAnalyzer.calculate_technical_indicators(df)
                if indicators is None:
                    continue
                
                # 거래량 비율 계산 (최근 거래량 vs 평균 거래량)
                recent_volume = candles[-1].volume
                avg_volume = np.mean([c.volume for c in candles[-20:]])
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
                
                # 패턴 감지
                patterns_found = []
                
                # 망치형 패턴 검사
                is_hammer, hammer_strength = PatternDetector.detect_hammer_pattern(candles)
                if is_hammer:
                    patterns_found.append((PatternType.HAMMER, hammer_strength))
                
                # 상승장악형 패턴 검사
                is_engulfing, engulfing_strength = PatternDetector.detect_bullish_engulfing_pattern(candles)
                if is_engulfing:
                    patterns_found.append((PatternType.BULLISH_ENGULFING, engulfing_strength))
                
                # 패턴이 발견된 경우 후보로 추가
                for pattern_type, pattern_strength in patterns_found:
                    # 시가총액 정보 (임시로 추정)
                    estimated_market_cap = current_price * 1000000  # 임시 추정값
                    market_cap_type = TechnicalAnalyzer.get_market_cap_type(estimated_market_cap)
                    
                    # 목표가 계산
                    target_price = self.calculate_target_price(
                        current_price, 
                        indicators.atr, 
                        pattern_strength,
                        market_cap_type
                    )
                    
                    # 손절매 계산 (패턴 저점 하향 돌파)
                    if pattern_type == PatternType.HAMMER:
                        stop_loss = candles[-1].low_price * 0.98
                    else:  # BULLISH_ENGULFING
                        stop_loss = min(candles[-2].low_price, candles[-1].low_price) * 0.98
                    
                    # 기술적 점수 계산
                    technical_score = TechnicalAnalyzer.calculate_technical_score(indicators, current_price)
                    
                    # 신뢰도 계산
                    confidence = PatternDetector.get_pattern_confidence(
                        pattern_type, pattern_strength, volume_ratio, technical_score
                    )
                    
                    # 필터링 조건
                    if (confidence >= 60.0 and  # 신뢰도 60% 이상
                        volume_ratio >= 1.2 and  # 거래량 20% 이상 증가
                        technical_score >= 3.0):  # 기술적 점수 3점 이상
                        
                        candidate = PatternResult(
                            stock_code=stock_code,
                            stock_name=stock_name,
                            pattern_type=pattern_type,
                            pattern_strength=pattern_strength,
                            current_price=current_price,
                            target_price=target_price,
                            stop_loss=stop_loss,
                            market_cap_type=market_cap_type,
                            volume_ratio=volume_ratio,
                            technical_score=technical_score,
                            pattern_date=candles[-1].date,
                            confidence=confidence
                        )
                        candidates.append(candidate)
                
                processed_count += 1
                if processed_count % 50 == 0:
                    self.logger.info(f"진행률: {processed_count}/{len(stocks)} ({processed_count/len(stocks)*100:.1f}%)")
                
                # 제한 수량 도달 시 중단
                if len(candidates) >= limit:
                    break
                    
            except Exception as e:
                self.logger.error(f"종목 {stock.get('code', 'Unknown')} 처리 실패: {e}")
                continue
        
        # 신뢰도 순으로 정렬
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        self.logger.info(f"스캔 완료: {len(candidates)}개 후보 종목 발견")
        return candidates
    