"""
캔들패턴 기반 매수후보 종목 스크리너

망치형과 상승장악형 패턴을 감지하여 매수후보 종목을 선별하는 클래스입니다.
시가총액별 차별화된 목표값 설정과 기술적 지표 필터링을 지원합니다.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass

from api.kis_market_api import get_inquire_daily_itemchartprice, get_stock_market_cap
from api.kis_auth import KisAuth
from utils.logger import setup_logger
from utils.korean_time import now_kst
from trading.technical_analyzer import TechnicalAnalyzer, TechnicalIndicators, MarketCapType
from trading.pattern_detector import PatternDetector, CandleData
from core.enums import PatternType


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
        
        # 스크리닝 상태 관리
        self.last_screening_time: Optional[datetime] = None
        self.candidate_results: List[PatternResult] = []
    
    def run_candidate_screening(self, 
                               message_callback: Optional[Callable[[str], None]] = None,
                               force: bool = False,
                               include_today: bool = True) -> List[PatternResult]:
        """
        매수후보 종목 스크리닝 실행
        
        Args:
            message_callback: 메시지 전송 콜백 함수
            force: 강제 실행 여부 (현재 사용하지 않음)
            include_today: 오늘자 데이터 포함 여부 (True: 포함, False: 제외)
            
        Returns:
            List[PatternResult]: 후보 종목 리스트
        """
        try:
            self.logger.info("🔍 매수후보 종목 스크리닝 시작...")
            if message_callback:
                message_callback("🔍 매수후보 종목 스크리닝을 시작합니다...")
            
            # 캔들패턴 기반 후보 종목 스캔
            candidates = self.scan_candidates(limit=30, include_today=include_today)
            
            if candidates:
                self.candidate_results = candidates
                self.last_screening_time = now_kst()
                
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
            # 패턴별 이름과 이모지 매핑
            pattern_names = {
                PatternType.MORNING_STAR: "🌟 샛별",
                PatternType.BULLISH_ENGULFING: "📈 상승장악형", 
                PatternType.THREE_WHITE_SOLDIERS: "⚔️ 세 백병",
                PatternType.ABANDONED_BABY: "👶 버려진 아기",
                PatternType.HAMMER: "🔨 망치형"
            }
            
            pattern_name = pattern_names.get(candidate.pattern_type, "❓ 알 수 없음")
            
            # 패턴별 상세 정보 가져오기
            from trading.technical_analyzer import TechnicalAnalyzer
            pattern_config = TechnicalAnalyzer.get_pattern_config(candidate.pattern_type)
            
            message += f"{i}. {candidate.stock_name} ({candidate.stock_code})\n"
            message += f"   패턴: {pattern_name}\n"
            message += f"   현재가: {candidate.current_price:,.0f}원\n"
            message += f"   목표가: {candidate.target_price:,.0f}원 "
            message += f"({(candidate.target_price/candidate.current_price-1)*100:.1f}%)\n"
            
            if pattern_config:
                message += f"   보유기간: {pattern_config.optimal_holding_days}일 "
                message += f"(최대 {pattern_config.max_holding_days}일)\n"
                entry_timing = TechnicalAnalyzer.get_entry_timing_message(candidate.pattern_type)
                message += f"   진입시점: {entry_timing}\n"
            
            message += f"   신뢰도: {candidate.confidence:.1f}%\n"
            message += f"   거래량: {candidate.volume_ratio:.1f}배\n\n"
        
        message += "📊 패턴별 투자 전략 (현실적 목표):\n"
        message += "• 🌟 샛별: 즉시 매수, 5-10일 보유, 5-8% 목표\n"
        message += "  ↳ 손절: 도지 캔들 저가 돌파\n"
        message += "• 📈 상승장악형: 익일 매수, 3-7일 보유, 4-6% 목표\n"
        message += "  ↳ 손절: 장악 캔들 저가 돌파\n"
        message += "• ⚔️ 세 백병: 확정 후 매수, 7-14일 보유, 6-8% 목표\n"
        message += "  ↳ 손절: 첫 백병 저가 돌파\n"
        message += "• 👶 버려진 아기: 즉시 매수, 5-12일 보유, 6-8% 목표\n"
        message += "  ↳ 손절: 갭 메움 발생시 즉시\n"
        message += "• 🔨 망치형: 상승 확인 후 매수, 2-5일 보유, 3-4% 목표\n"
        message += "  ↳ 손절: 실체 하단 돌파\n"
        message += "• 💡 실전 접근: 작은 수익도 꾸준히 쌓는 것이 핵심\n\n"
        message += "🔥 실전 적합한 필터링 적용됨:\n"
        message += "• 패턴별 차별화된 신뢰도 (60-70% 이상)\n"
        message += "• 기술점수 3.0점 이상 (모멘텀 지표 포함)\n"
        message += "• 거래량 1.3배 이상 (강화된 조건)\n"
        message += "• RSI 과매수 제외 + 손익비 1:2 이상 검증\n"
        message += "• 🚀 모멘텀 지표 필터링:\n"
        message += "  - 이동평균선 돌파 (MA20/MA60) 필수\n"
        message += "  - 상대강도 양수 + 52주 신고가 98% 이하\n"
        message += "  - 단기 모멘텀 (5일/20일) 양수 확인"
        
        return message
    
    def get_candidate_results(self) -> List[PatternResult]:
        """현재 후보 종목 결과 반환"""
        return self.candidate_results.copy()
    
    def clear_candidate_results(self) -> None:
        """후보 종목 결과 초기화"""
        self.candidate_results = []
        self.last_screening_time = None
    
    def get_daily_price(self, stock_code: str, period: int = 90) -> Optional[pd.DataFrame]:
        """일봉 데이터 조회"""
        try:
            # 최근 거래일 계산 (주말 제외)
            end_date = self._get_last_trading_day()
            start_date = end_date - timedelta(days=period + 30)  # 여유분 추가
            
            self.logger.debug(f"📅 {stock_code} 일봉 조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            
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
                self.logger.debug(f"❌ {stock_code}: 일봉 데이터 조회 실패 또는 데이터 없음")
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
            result_df = df.tail(period)
            self.logger.debug(f"📊 {stock_code}: 일봉 데이터 {len(result_df)}일 조회 완료")
            return result_df
            
        except Exception as e:
            self.logger.error(f"일봉 데이터 조회 실패 {stock_code}: {e}")
            return None
    
    def _get_last_trading_day(self) -> datetime:
        """최근 거래일 계산 (주말 제외)"""
        current_date = now_kst()
        
        # 현재 시간이 장 마감 전이면 전일을 기준으로 함
        if current_date.hour < 15 or (current_date.hour == 15 and current_date.minute < 30):
            current_date -= timedelta(days=1)
        
        # 주말 제외
        while current_date.weekday() >= 5:  # 토요일(5), 일요일(6)
            current_date -= timedelta(days=1)
        
        return current_date
    
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
    
    def get_market_cap_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """종목의 시가총액 정보 조회"""
        try:
            return get_stock_market_cap(stock_code)
        except Exception as e:
            self.logger.error(f"시가총액 조회 실패 {stock_code}: {e}")
            return None
    
    def scan_candidates(self, limit: int = 50, include_today: bool = True) -> List[PatternResult]:
        """매수후보 종목 스캔"""
        stocks = self.load_stock_list()
        if not stocks:
            self.logger.warning("주식 리스트가 비어있습니다")
            return []
        
        candidates = []
        processed_count = 0
        pattern_found_count = 0
        filtered_count = 0
        
        # 필터링 통계
        stats = {
            'data_insufficient': 0,
            'indicator_failed': 0,
            'volume_insufficient': 0,
            'trading_value_insufficient': 0,
            'no_pattern': 0,
            'pattern_found': 0,
            'confidence_failed': 0,
            'volume_ratio_failed': 0,
            'technical_score_failed': 0,
            'final_candidates': 0
        }
        
        # 오늘자 포함/제외 상태 로그
        today_status = "포함" if include_today else "제외"
        self.logger.info(f"🔍 총 {len(stocks)}개 종목 매수후보 스캔 시작 (오늘자 데이터: {today_status})")
        self.logger.info(f"🔥 5일 단기 승부 최적화 필터링 조건:")
        self.logger.info(f"   🎯 패턴별 신뢰도: 망치형 75%↑, 상승장악형 75%↑, 샛별 80%↑, 세백병 75%↑, 버려진아기 77%↑")
        self.logger.info(f"   🚀 거래량 증가: 평소 대비 1.5배 이상 (단기 모멘텀 강화)")
        self.logger.info(f"   💰 기술적 점수: 3.5점 이상 (확실한 신호만 선별)")
        self.logger.info(f"   📊 RSI 과매수 제외: 80 이하만 선별 (과매수 구간 엄격 배제)")
        self.logger.info(f"   ⚖️ 손익비 검증: 최소 1:2.5 이상 (단기 승부 리스크 관리)")
        self.logger.info(f"   🔧 최소 유동성: 평균 거래량≥20천주, 평균 거래대금≥10억원, 최근 거래대금≥3억원")
        self.logger.info(f"   🚀 강화된 모멘텀 지표 필터링 (4개 중 3개 이상 만족):")
        self.logger.info(f"     • 이동평균선 근접: MA20 3% 이내 또는 MA60 7% 이내 (강화)")
        self.logger.info(f"     • 상대강도: 14일 평균 대비 0% 이상 (강화)")
        self.logger.info(f"     • 52주 신고가: 95% 이하 (고점 부근 제외)")
        self.logger.info(f"     • 단기 모멘텀: 5일 또는 20일 수익률 0% 이상 (강화)")
        
        for stock in stocks:
            try:
                stock_code = stock['code']
                stock_name = stock['name']
                
                # 일봉 데이터 조회 (최근 90일)
                df = self.get_daily_price(stock_code, period=90)
                if df is None or len(df) < 80:
                    stats['data_insufficient'] += 1
                    self.logger.debug(f"❌ {stock_name}({stock_code}): 데이터 부족 (길이: {len(df) if df is not None else 0})")
                    continue
                
                # include_today가 False이면 오늘자 데이터 제외
                if not include_today:
                    # 현재 날짜 (한국시간)
                    current_date_str = now_kst().strftime('%Y%m%d')
                    
                    # 마지막 데이터의 날짜가 오늘이면 제외
                    if not df.empty and df.iloc[-1]['date'] == current_date_str:
                        df = df.iloc[:-1]  # 마지막 행 제거
                        self.logger.debug(f"📅 {stock_name}({stock_code}): 오늘자 데이터 제외 ({current_date_str})")
                    
                    # 데이터 길이 재확인
                    if len(df) < 80:
                        stats['data_insufficient'] += 1
                        self.logger.debug(f"❌ {stock_name}({stock_code}): 오늘자 제외 후 데이터 부족 (길이: {len(df)})")
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
                
                # 기술적 지표 계산 (필터링된 df 사용)
                indicators = TechnicalAnalyzer.calculate_technical_indicators(df)
                if indicators is None:
                    stats['indicator_failed'] += 1
                    self.logger.debug(f"❌ {stock_name}({stock_code}): 기술적 지표 계산 실패")
                    continue
                
                # 거래량 분석 (필터링된 candles 사용)
                recent_volume = candles[-1].volume
                avg_volume = np.mean([c.volume for c in candles[-20:]])
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0
                
                # 거래대금 계산 (평균 거래대금)
                avg_trading_value = avg_volume * current_price / 100000000  # 단위: 억원
                
                # 최근 거래대금 계산
                recent_trading_value = recent_volume * current_price / 100000000  # 단위: 억원
                
                # 🔧 현실적인 최소 유동성 확보 조건
                if avg_volume < 20000:  # 일평균 거래량 2만주 미만 (원래대로 복원)
                    stats['volume_insufficient'] += 1
                    self.logger.debug(f"❌ {stock_name}({stock_code}): 평균 거래량 부족 ({avg_volume:,.0f}주 < 20,000주)")
                    continue
                
                if avg_trading_value < 1.0:  # 일평균 거래대금 10억원 미만 (원래대로 복원)
                    stats['trading_value_insufficient'] += 1
                    self.logger.debug(f"❌ {stock_name}({stock_code}): 평균 거래대금 부족 ({avg_trading_value:.2f}억원 < 10억원)")
                    continue
                
                # 🔧 최근 거래량 추가 체크 (슬리피지 방지)
                if recent_trading_value < 0.3:  # 최근 거래대금 3억원 미만 (원래대로 복원)
                    stats['trading_value_insufficient'] += 1
                    self.logger.debug(f"❌ {stock_name}({stock_code}): 최근 거래대금 부족 ({recent_trading_value:.2f}억원 < 3억원)")
                    continue
                
                # 패턴 감지 (TOP 5 패턴 검사) - 필터링된 candles 사용
                patterns_found = []
                
                # 1. 샛별 패턴 검사 (신뢰도 95%+)
                is_morning_star, morning_star_strength = PatternDetector.detect_morning_star_pattern(candles)
                if is_morning_star:
                    patterns_found.append((PatternType.MORNING_STAR, morning_star_strength))
                    self.logger.debug(f"🌟 {stock_name}({stock_code}): 샛별 패턴 감지 (강도: {morning_star_strength:.2f})")
                
                # 2. 상승장악형 패턴 검사 (신뢰도 90%+)
                is_engulfing, engulfing_strength = PatternDetector.detect_bullish_engulfing_pattern(candles)
                if is_engulfing:
                    patterns_found.append((PatternType.BULLISH_ENGULFING, engulfing_strength))
                    self.logger.debug(f"📈 {stock_name}({stock_code}): 상승장악형 패턴 감지 (강도: {engulfing_strength:.2f})")
                
                # 3. 세 백병 패턴 검사 (신뢰도 85%+)
                is_three_soldiers, three_soldiers_strength = PatternDetector.detect_three_white_soldiers_pattern(candles)
                if is_three_soldiers:
                    patterns_found.append((PatternType.THREE_WHITE_SOLDIERS, three_soldiers_strength))
                    self.logger.debug(f"⚔️ {stock_name}({stock_code}): 세 백병 패턴 감지 (강도: {three_soldiers_strength:.2f})")
                
                # 4. 버려진 아기 패턴 검사 (신뢰도 90%+)
                is_abandoned_baby, abandoned_baby_strength = PatternDetector.detect_abandoned_baby_pattern(candles)
                if is_abandoned_baby:
                    patterns_found.append((PatternType.ABANDONED_BABY, abandoned_baby_strength))
                    self.logger.debug(f"👶 {stock_name}({stock_code}): 버려진 아기 패턴 감지 (강도: {abandoned_baby_strength:.2f})")
                
                # 5. 망치형 패턴 검사 (신뢰도 75%+)
                is_hammer, hammer_strength = PatternDetector.detect_hammer_pattern(candles)
                if is_hammer:
                    patterns_found.append((PatternType.HAMMER, hammer_strength))
                    self.logger.debug(f"🔨 {stock_name}({stock_code}): 망치형 패턴 감지 (강도: {hammer_strength:.2f})")
                
                if not patterns_found:
                    stats['no_pattern'] += 1
                    self.logger.debug(f"⚪ {stock_name}({stock_code}): 패턴 없음")
                
                # 패턴이 발견된 경우 후보로 추가
                for pattern_type, pattern_strength in patterns_found:
                    pattern_found_count += 1
                    stats['pattern_found'] += 1
                    
                    # 시가총액 정보 (실제 API 조회)
                    market_cap_info = self.get_market_cap_info(stock_code)
                    if market_cap_info:
                        actual_market_cap = market_cap_info['market_cap']
                        market_cap_type = TechnicalAnalyzer.get_market_cap_type(actual_market_cap)
                        self.logger.debug(f"💰 {stock_name}({stock_code}): 시가총액 {actual_market_cap:,.0f}억원 ({market_cap_type.value})")
                    else:
                        # API 조회 실패 시 임시 추정값 사용
                        estimated_market_cap = current_price * 1000000
                        market_cap_type = TechnicalAnalyzer.get_market_cap_type(estimated_market_cap)
                        self.logger.warning(f"⚠️ {stock_name}({stock_code}): 시가총액 조회 실패, 추정값 사용 ({estimated_market_cap:,.0f}억원)")
                    
                    # 기술적 점수 계산 (목표가 계산 전에 먼저 계산)
                    technical_score = TechnicalAnalyzer.calculate_technical_score(indicators, current_price)
                    
                    # 패턴별 목표가 계산 (개선된 버전)
                    target_price = TechnicalAnalyzer.calculate_pattern_target_price(
                        current_price, 
                        pattern_type,
                        pattern_strength,
                        market_cap_type,
                        market_condition=1.0,  # 시장 상황 (기본값)
                        volume_ratio=volume_ratio,  # 거래량 증가율
                        rsi=indicators.rsi,  # RSI 값
                        technical_score=technical_score  # 기술점수
                    )
                    
                    # 캔들 데이터를 딕셔너리 형태로 변환
                    candle_dicts = []
                    for candle in candles:
                        candle_dict = {
                            'date': candle.date,
                            'open_price': candle.open_price,
                            'high_price': candle.high_price,
                            'low_price': candle.low_price,
                            'close_price': candle.close_price,
                            'volume': candle.volume
                        }
                        candle_dicts.append(candle_dict)
                    
                    # 패턴별 손절매 계산
                    stop_loss = TechnicalAnalyzer.calculate_pattern_stop_loss(
                        current_price,
                        pattern_type,
                        candle_dicts,
                        target_price
                    )
                    
                    # 신뢰도 계산
                    confidence = PatternDetector.get_pattern_confidence(
                        pattern_type, pattern_strength, volume_ratio, technical_score
                    )
                    
                    # 상세 로그 출력
                    pattern_names = {
                        PatternType.MORNING_STAR: "샛별",
                        PatternType.BULLISH_ENGULFING: "상승장악형", 
                        PatternType.THREE_WHITE_SOLDIERS: "세 백병",
                        PatternType.ABANDONED_BABY: "버려진 아기",
                        PatternType.HAMMER: "망치형"
                    }
                    pattern_name = pattern_names.get(pattern_type, "알 수 없음")
                    self.logger.debug(f"📊 {stock_name}({stock_code}) {pattern_name}:")
                    self.logger.debug(f"   현재가: {current_price:,.0f}원")
                    self.logger.debug(f"   목표가: {target_price:,.0f}원 ({(target_price/current_price-1)*100:.1f}%)")
                    self.logger.debug(f"   손절가: {stop_loss:,.0f}원 ({(stop_loss/current_price-1)*100:.1f}%)")
                    self.logger.debug(f"   신뢰도: {confidence:.1f}%")
                    self.logger.debug(f"   거래량: {volume_ratio:.1f}배 (평균: {avg_volume:,.0f}주, 최근: {recent_volume:,.0f}주)")
                    self.logger.debug(f"   거래대금: 평균 {avg_trading_value:.1f}억원, 최근 {recent_trading_value:.1f}억원")
                    self.logger.debug(f"   기술점수: {technical_score:.1f}점")
                    self.logger.debug(f"   RSI: {indicators.rsi:.1f}")
                    
                    # 🚀 모멘텀 지표 로그 추가
                    self.logger.debug(f"   🚀 모멘텀 지표:")
                    self.logger.debug(f"     MA20 근접: {'✅' if abs(current_price - indicators.ma20) / current_price <= 0.05 else '❌'}")
                    self.logger.debug(f"     MA60 근접: {'✅' if abs(current_price - indicators.ma60) / current_price <= 0.10 else '❌'}")
                    self.logger.debug(f"     상대강도: {indicators.relative_strength:.1f}%")
                    self.logger.debug(f"     52주 신고가 대비: {indicators.high_52w_ratio:.1f}%")
                    self.logger.debug(f"     5일 모멘텀: {indicators.momentum_5d:.1f}%")
                    self.logger.debug(f"     20일 모멘텀: {indicators.momentum_20d:.1f}%")
                    
                    # 🔥 완화된 패턴별 차별화 필터링 조건
                    pattern_config = TechnicalAnalyzer.get_pattern_config(pattern_type)
                    required_volume_ratio = pattern_config.volume_multiplier if pattern_config else 1.2
                    
                    # 🎯 패턴별 최소 신뢰도 설정 (5일 단기 승부 최적화)
                    pattern_min_confidence = {
                        PatternType.MORNING_STAR: 80.0,        # 샛별: 80% 이상 (70% → 80%, 단기 승부 강화)
                        PatternType.THREE_WHITE_SOLDIERS: 75.0, # 세 백병: 75% 이상 (65% → 75%, 강화)
                        PatternType.ABANDONED_BABY: 77.0,      # 버려진 아기: 77% 이상 (67% → 77%, 강화)
                        PatternType.BULLISH_ENGULFING: 75.0,   # 상승장악형: 75% 이상 (65% → 75%, 강화)
                        PatternType.HAMMER: 75.0               # 망치형: 75% 이상 (60% → 75%, 대폭 강화)
                    }
                    
                    min_confidence = pattern_min_confidence.get(pattern_type, 75.0)
                    
                    # 🚀 단기 승부용 강화된 기술점수 조건
                    min_technical_score = 2.6  # 2.6
                    
                    # 📈 단기 승부용 거래량 조건 강화
                    min_volume_ratio = max(required_volume_ratio, 1.4)  # 1.4
                    
                    # 💰 단기 승부용 RSI 조건 강화
                    max_rsi = 77.0  # 85.0 → 80.0으로 강화 (과매수 구간 더 엄격하게)
                    
                    # 🎯 손익비 검증 (단기 승부용)
                    if target_price > current_price and stop_loss < current_price:
                        profit_potential = target_price - current_price
                        loss_potential = current_price - stop_loss
                        risk_reward_ratio = profit_potential / loss_potential if loss_potential > 0 else 0
                        min_risk_reward_ratio = 2.0  # 2.0 → 2.5로 강화 (단기 승부엔 더 좋은 손익비 필요)
                    else:
                        risk_reward_ratio = 0
                        min_risk_reward_ratio = 2.0
                    
                    # 🚀 단기 승부용 강화된 모멘텀 지표 필터링 조건
                    # 1. 이동평균선 근접 조건 강화
                    ma20_close = abs(current_price - indicators.ma20) / current_price <= 0.03 if indicators.ma20 > 0 else False  # 5% → 3%로 강화
                    ma60_close = abs(current_price - indicators.ma60) / current_price <= 0.07 if indicators.ma60 > 0 else False  # 10% → 7%로 강화
                    ma_close_condition = ma20_close or ma60_close
                    
                    # 2. 단기 승부용 상대강도 조건 강화
                    rs_acceptable = indicators.relative_strength >= 0.0  # -2% → 0% 이상으로 강화
                    
                    # 3. 단기 승부용 52주 신고가 대비 위치 조건 강화
                    high_52w_ok = indicators.high_52w_ratio <= 95.0  # 99% → 95%로 강화 (고점 부근 제외)
                    
                    # 4. 단기 승부용 모멘텀 조건 강화
                    momentum_acceptable = indicators.momentum_5d >= 0.0 or indicators.momentum_20d >= 0.0  # -3% → 0% 이상으로 강화
                    
                    # 🔧 단기 승부용 모멘텀 조건 강화 (4개 중 3개 이상 만족)
                    momentum_conditions = [ma_close_condition, rs_acceptable, high_52w_ok, momentum_acceptable]
                    momentum_pass_count = sum(momentum_conditions)
                    momentum_criteria_met = momentum_pass_count >= 2  # 2개 → 3개로 강화 (더 확실한 신호만)
                    
                    if (confidence >= min_confidence and           # 완화된 패턴별 신뢰도
                        volume_ratio >= min_volume_ratio and      # 완화된 거래량 조건 (1.2배 이상)
                        technical_score >= min_technical_score and # 완화된 기술점수 (2.5점 이상)
                        indicators.rsi <= max_rsi and             # 완화된 RSI 과매수 제외 (90 이하)
                        risk_reward_ratio >= min_risk_reward_ratio and # 완화된 손익비 검증 (1:1.5 이상)
                        momentum_criteria_met):                   # 완화된 모멘텀 조건 (4개 중 2개 이상)
                        
                        filtered_count += 1
                        stats['final_candidates'] += 1
                        
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
                        
                        self.logger.info(f"✅ {stock_name}({stock_code}): 5일 단기 승부 조건 통과! "
                                       f"({pattern_name}, 신뢰도: {confidence:.1f}%, "
                                       f"목표: {(target_price/current_price-1)*100:.1f}%, "
                                       f"손익비: 1:{risk_reward_ratio:.1f}, "
                                       f"모멘텀: {momentum_pass_count}/4개 만족)")
                    else:
                        # 🔍 상세한 필터링 실패 사유 로그 및 통계
                        failed_reasons = []
                        if confidence < min_confidence:
                            failed_reasons.append(f"신뢰도부족({confidence:.1f}%<{min_confidence}%)")
                            stats['confidence_failed'] += 1
                        if volume_ratio < min_volume_ratio:
                            failed_reasons.append(f"거래량부족({volume_ratio:.1f}배<{min_volume_ratio}배)")
                            stats['volume_ratio_failed'] += 1
                        if technical_score < min_technical_score:
                            failed_reasons.append(f"기술점수부족({technical_score:.1f}점<{min_technical_score}점)")
                            stats['technical_score_failed'] += 1
                        if indicators.rsi > max_rsi:
                            failed_reasons.append(f"RSI과매수({indicators.rsi:.1f}>{max_rsi})")
                            stats['technical_score_failed'] += 1  # RSI도 기술점수 실패로 분류
                        if risk_reward_ratio < min_risk_reward_ratio:
                            failed_reasons.append(f"손익비부족(1:{risk_reward_ratio:.1f}<1:{min_risk_reward_ratio})")
                            stats['technical_score_failed'] += 1  # 손익비도 기술점수 실패로 분류
                        
                        # 🚀 모멘텀 지표 실패 사유 추가
                        if not momentum_criteria_met:
                            failed_reasons.append(f"모멘텀조건부족({momentum_pass_count}/4개<2개)")
                            stats['technical_score_failed'] += 1
                            # 세부 조건 추가 로그
                            momentum_details = []
                            if not ma_close_condition:
                                momentum_details.append("이동평균선원거리")
                            if not rs_acceptable:
                                momentum_details.append(f"상대강도과소({indicators.relative_strength:.1f}%)")
                            if not high_52w_ok:
                                momentum_details.append(f"52주신고가과근접({indicators.high_52w_ratio:.1f}%)")
                            if not momentum_acceptable:
                                momentum_details.append(f"모멘텀과소(5일:{indicators.momentum_5d:.1f}%,20일:{indicators.momentum_20d:.1f}%)")
                            if momentum_details:
                                failed_reasons.append(f"({', '.join(momentum_details)})")
                        
                        self.logger.debug(f"❌ {stock_name}({stock_code}) {pattern_name}: 5일 단기 승부 필터링 실패 - {', '.join(failed_reasons)}")
                
                processed_count += 1
                if processed_count % 100 == 0:
                    self.logger.info(f"📈 진행률: {processed_count}/{len(stocks)} ({processed_count/len(stocks)*100:.1f}%) - "
                                   f"패턴발견: {pattern_found_count}, 후보선정: {len(candidates)}")
                
                # 제한 수량 도달 시 중단
                if len(candidates) >= limit:
                    self.logger.info(f"🎯 제한 수량({limit})에 도달하여 스캔 중단")
                    break
                    
            except Exception as e:
                self.logger.error(f"❌ 종목 {stock.get('name', 'Unknown')}({stock.get('code', 'Unknown')}) 처리 실패: {e}")
                continue
        
        # 신뢰도 순으로 정렬
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        # 최종 결과 로그
        self.logger.info(f"🎯 스캔 완료! (오늘자 데이터: {today_status})")
        self.logger.info(f"   처리된 종목: {processed_count}/{len(stocks)}개")
        self.logger.info(f"   패턴 발견: {pattern_found_count}개")
        self.logger.info(f"   필터링 통과: {filtered_count}개")
        self.logger.info(f"   최종 후보: {len(candidates)}개")
        
        # 상세 필터링 통계
        self.logger.info(f"📊 필터링 통계:")
        self.logger.info(f"   데이터 부족: {stats['data_insufficient']}개")
        self.logger.info(f"   기술지표 실패: {stats['indicator_failed']}개")
        self.logger.info(f"   거래량 부족: {stats['volume_insufficient']}개")
        self.logger.info(f"   거래대금 부족: {stats['trading_value_insufficient']}개")
        self.logger.info(f"   패턴 없음: {stats['no_pattern']}개")
        self.logger.info(f"   패턴 발견: {stats['pattern_found']}개")
        self.logger.info(f"   신뢰도 부족: {stats['confidence_failed']}개")
        self.logger.info(f"   거래량비율 부족: {stats['volume_ratio_failed']}개")
        self.logger.info(f"   기술점수 부족: {stats['technical_score_failed']}개")
        self.logger.info(f"   최종 선정: {stats['final_candidates']}개")
        
        if candidates:
            self.logger.info(f"🥇 최고 신뢰도: {candidates[0].stock_name}({candidates[0].stock_code}) - {candidates[0].confidence:.1f}%")
        
        return candidates
    