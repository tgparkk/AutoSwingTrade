"""
기존 포지션 목표가 업데이트 스크립트

개선된 패턴별 목표가 계산 로직에 맞게 기존 포지션들의 목표가를 재계산하여 업데이트합니다.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from api.kis_market_api import get_inquire_daily_itemchartprice
from api.kis_auth import KisAuth
from trading.technical_analyzer import TechnicalAnalyzer, MarketCapType
from trading.pattern_detector import PatternDetector, CandleData
from trading.candidate_screener import CandidateScreener
from core.enums import PatternType
from utils.logger import setup_logger
from utils.korean_time import now_kst


class PositionTargetUpdater:
    """포지션 목표가 업데이트 클래스"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        """
        초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.logger = setup_logger(__name__)
        
        # KIS API 초기화
        self.auth = KisAuth()
        if not self.auth.initialize():
            self.logger.warning("⚠️ KIS API 초기화 실패 - 일부 기능 제한됨")
        
        self.screener = CandidateScreener(self.auth)
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """
        활성 포지션 목록 조회
        
        Returns:
            List[Dict]: 활성 포지션 정보 리스트
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM positions 
                WHERE (status = 'ACTIVE' OR status = '활성') AND quantity > 0
                ORDER BY entry_time DESC
            """)
            
            positions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            self.logger.info(f"✅ 활성 포지션 {len(positions)}개 조회 완료")
            return positions
            
        except Exception as e:
            self.logger.error(f"❌ 활성 포지션 조회 실패: {e}")
            return []
    
    def get_candle_data(self, stock_code: str, period: int = 90) -> Optional[List[CandleData]]:
        """
        캔들 데이터 조회
        
        Args:
            stock_code: 종목코드
            period: 조회 기간 (일)
            
        Returns:
            Optional[List[CandleData]]: 캔들 데이터 리스트
        """
        try:
            df = self.screener.get_daily_price(stock_code, period)
            if df is None or len(df) < 80:
                return None
            
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
            
            return candles
            
        except Exception as e:
            self.logger.error(f"❌ {stock_code} 캔들 데이터 조회 실패: {e}")
            return None
    
    def calculate_new_target_price(self, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        새로운 목표가 계산
        
        Args:
            position: 포지션 정보
            
        Returns:
            Optional[Dict[str, float]]: 새로운 목표가 정보 {'target_price': float, 'stop_loss': float}
        """
        try:
            stock_code = position['stock_code']
            stock_name = position['stock_name']
            current_price = position['avg_price']  # 진입가 기준
            pattern_type_str = position.get('pattern_type')
            
            self.logger.info(f"🔄 {stock_name}({stock_code}) 목표가 재계산 시작...")
            
            # 패턴 타입 변환
            if not pattern_type_str:
                self.logger.warning(f"⚠️ {stock_name}: 패턴 타입 정보 없음, 기본 계산 적용")
                pattern_type = PatternType.MORNING_STAR  # 기본값
            else:
                try:
                    pattern_type = PatternType(pattern_type_str)
                except ValueError:
                    self.logger.warning(f"⚠️ {stock_name}: 알 수 없는 패턴 타입 '{pattern_type_str}', 기본 계산 적용")
                    pattern_type = PatternType.MORNING_STAR
            
            # 캔들 데이터 조회
            candles = self.get_candle_data(stock_code)
            if not candles:
                self.logger.error(f"❌ {stock_name}: 캔들 데이터 조회 실패")
                return None
            
            # DataFrame 변환 (기술적 지표 계산용)
            df_data = []
            for candle in candles:
                df_data.append({
                    'date': candle.date,
                    'open': candle.open_price,
                    'high': candle.high_price,
                    'low': candle.low_price,
                    'close': candle.close_price,
                    'volume': candle.volume
                })
            df = pd.DataFrame(df_data)
            
            # 기술적 지표 계산
            indicators = TechnicalAnalyzer.calculate_technical_indicators(df)
            if not indicators:
                self.logger.error(f"❌ {stock_name}: 기술적 지표 계산 실패")
                return None
            
            # 거래량 비율 계산
            import numpy as np
            recent_volume = candles[-1].volume
            avg_volume = np.mean([c.volume for c in candles[-20:]])
            volume_ratio = float(recent_volume / avg_volume) if avg_volume > 0 else 1.0
            
            # 시가총액 정보 조회
            market_cap_info = self.screener.get_market_cap_info(stock_code)
            if market_cap_info:
                market_cap = market_cap_info['market_cap']
                market_cap_type = TechnicalAnalyzer.get_market_cap_type(market_cap)
            else:
                # 추정값 사용
                estimated_market_cap = current_price * 1000000
                market_cap_type = TechnicalAnalyzer.get_market_cap_type(estimated_market_cap)
                self.logger.warning(f"⚠️ {stock_name}: 시가총액 조회 실패, 추정값 사용")
            
            # 기술적 점수 계산
            technical_score = TechnicalAnalyzer.calculate_technical_score(indicators, current_price)
            
            # 패턴 강도 (기존 값 사용 또는 기본값)
            pattern_strength = position.get('pattern_strength', 2.0)
            
            # 신뢰도 계산
            confidence = PatternDetector.get_pattern_confidence(
                pattern_type, pattern_strength, volume_ratio, technical_score
            )
            
            # 🔧 새로운 목표가 계산
            new_target_price = TechnicalAnalyzer.calculate_pattern_target_price(
                current_price,
                pattern_type,
                pattern_strength,
                market_cap_type,
                market_condition=1.0,
                volume_ratio=volume_ratio,
                rsi=indicators.rsi,
                technical_score=technical_score
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
            
            # 🔧 새로운 손절가 계산
            new_stop_loss = TechnicalAnalyzer.calculate_pattern_stop_loss(
                current_price,
                pattern_type,
                candle_dicts,
                new_target_price
            )
            
            # 결과 로그
            old_target = position.get('take_profit_price', 0)
            old_stop_loss = position.get('stop_loss_price', 0)
            
            self.logger.info(f"📊 {stock_name}({stock_code}) 목표가 재계산 완료:")
            self.logger.info(f"   패턴: {pattern_type.value}, 신뢰도: {confidence:.1f}%")
            self.logger.info(f"   진입가: {current_price:,.0f}원")
            self.logger.info(f"   목표가: {old_target:,.0f}원 → {new_target_price:,.0f}원 ({(new_target_price/current_price-1)*100:+.1f}%)")
            self.logger.info(f"   손절가: {old_stop_loss:,.0f}원 → {new_stop_loss:,.0f}원 ({(new_stop_loss/current_price-1)*100:+.1f}%)")
            self.logger.info(f"   거래량: {volume_ratio:.1f}배, 기술점수: {technical_score:.1f}점")
            
            return {
                'target_price': float(new_target_price),
                'stop_loss': float(new_stop_loss),
                'confidence': float(confidence),
                'pattern_type': pattern_type.value
            }
            
        except Exception as e:
            self.logger.error(f"❌ {position['stock_name']} 목표가 계산 실패: {e}")
            return None
    
    def update_position_target(self, stock_code: str, new_data: Dict[str, float]) -> bool:
        """
        포지션 목표가 업데이트
        
        Args:
            stock_code: 종목코드
            new_data: 새로운 목표가 정보
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE positions SET
                    take_profit_price = ?,
                    stop_loss_price = ?,
                    last_update = ?,
                    entry_reason = ?
                WHERE stock_code = ?
            """, (
                new_data['target_price'],
                new_data['stop_loss'],
                now_kst().strftime('%Y-%m-%d %H:%M:%S'),
                f"패턴: {new_data['pattern_type']}, 신뢰도: {new_data['confidence']:.1f}% (업데이트됨)",
                stock_code
            ))
            
            conn.commit()
            conn.close()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"❌ {stock_code} 포지션 업데이트 실패: {e}")
            return False
    
    def update_all_positions(self, confirm: bool = False) -> None:
        """
        모든 활성 포지션의 목표가 업데이트
        
        Args:
            confirm: 실제 업데이트 여부 (False면 시뮬레이션만)
        """
        try:
            positions = self.get_active_positions()
            if not positions:
                self.logger.warning("⚠️ 업데이트할 활성 포지션이 없습니다")
                return
            
            if not confirm:
                self.logger.info("🔍 시뮬레이션 모드: 실제 업데이트하지 않습니다")
            
            success_count = 0
            total_count = len(positions)
            
            self.logger.info(f"🔄 총 {total_count}개 포지션 목표가 업데이트 시작...")
            
            for i, position in enumerate(positions, 1):
                stock_code = position['stock_code']
                stock_name = position['stock_name']
                
                self.logger.info(f"📊 [{i}/{total_count}] {stock_name}({stock_code}) 처리 중...")
                
                # 새로운 목표가 계산
                new_data = self.calculate_new_target_price(position)
                if not new_data:
                    self.logger.error(f"❌ {stock_name}: 목표가 계산 실패, 건너뜀")
                    continue
                
                # 실제 업데이트 (confirm=True인 경우)
                if confirm:
                    if self.update_position_target(stock_code, new_data):
                        success_count += 1
                        self.logger.info(f"✅ {stock_name}: 목표가 업데이트 완료")
                    else:
                        self.logger.error(f"❌ {stock_name}: 데이터베이스 업데이트 실패")
                else:
                    success_count += 1
                    self.logger.info(f"✅ {stock_name}: 시뮬레이션 완료")
            
            if confirm:
                self.logger.info(f"🎉 목표가 업데이트 완료: {success_count}/{total_count}개 성공")
            else:
                self.logger.info(f"🎉 시뮬레이션 완료: {success_count}/{total_count}개 계산 성공")
                self.logger.info("💡 실제 업데이트하려면 confirm=True로 실행하세요")
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 업데이트 과정에서 오류 발생: {e}")


def main():
    """메인 함수"""
    logger = setup_logger(__name__)
    
    logger.info("🚀 포지션 목표가 업데이트 스크립트 시작")
    
    # 업데이트 클래스 초기화
    updater = PositionTargetUpdater()
    
    # 사용자 확인
    print("\n" + "="*80)
    print("📊 기존 포지션 목표가 업데이트")
    print("="*80)
    print("새로운 패턴별 목표가 계산 로직에 맞게 기존 포지션들의 목표가를 업데이트합니다.")
    print("\n옵션:")
    print("1. 시뮬레이션만 실행 (실제 업데이트 X)")
    print("2. 실제 업데이트 실행")
    print("3. 종료")
    
    while True:
        try:
            choice = input("\n선택하세요 (1/2/3): ").strip()
            
            if choice == "1":
                logger.info("🔍 시뮬레이션 모드로 실행합니다...")
                updater.update_all_positions(confirm=False)
                break
            elif choice == "2":
                confirm = input("⚠️ 실제로 데이터베이스를 업데이트하시겠습니까? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    logger.info("✅ 실제 업데이트 모드로 실행합니다...")
                    updater.update_all_positions(confirm=True)
                else:
                    logger.info("❌ 업데이트가 취소되었습니다.")
                break
            elif choice == "3":
                logger.info("👋 스크립트를 종료합니다.")
                break
            else:
                print("❌ 잘못된 선택입니다. 1, 2, 3 중 하나를 선택하세요.")
        except KeyboardInterrupt:
            logger.info("\n👋 사용자에 의해 중단되었습니다.")
            break
        except Exception as e:
            logger.error(f"❌ 입력 처리 중 오류: {e}")


if __name__ == "__main__":
    main() 