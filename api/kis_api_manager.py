"""
KIS API Manager - 모든 KIS API 모듈들을 통합 관리하는 메인 API 매니저

한국투자증권 KIS API의 모든 기능을 통합하여 관리하고,
스레들이 쉽게 사용할 수 있는 고수준 인터페이스를 제공합니다.
"""
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, cast
from dataclasses import dataclass
import pandas as pd

from . import kis_auth
from . import kis_account_api
from . import kis_market_api
from . import kis_order_api
from utils.logger import setup_logger
from utils.korean_time import now_kst


@dataclass
class OrderResult:
    """주문 결과 정보"""
    success: bool
    order_id: str = ""
    message: str = ""
    error_code: str = ""
    data: Optional[Dict[str, Any]] = None


@dataclass
class StockPrice:
    """주식 가격 정보"""
    stock_code: str
    current_price: float
    change_amount: float
    change_rate: float
    volume: int
    timestamp: datetime


@dataclass
class AccountInfo:
    """계좌 정보"""
    account_balance: float
    available_amount: float
    stock_value: float
    total_value: float
    positions: List[Dict[str, Any]]


class KISAPIManager:
    """KIS API Manager - 모든 KIS API 기능을 통합 관리"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.is_initialized = False
        self.is_authenticated = False
        self.last_auth_time = None
        
        # API 호출 통계
        self.call_count = 0
        self.error_count = 0
        self.last_call_time = time.time()
        
        # 실패 재시도 설정
        self.max_retries = 3
        self.retry_delay = 1.0
        
    def initialize(self) -> bool:
        """API 매니저 초기화"""
        try:
            self.logger.info("KIS API Manager 초기화 시작...")
            
            # 1. KIS 인증 초기화
            if not self._initialize_auth():
                return False
            
            # 2. 기본 설정 확인
            if not self._validate_settings():
                return False
            
            self.is_initialized = True
            self.logger.info("✅ KIS API Manager 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ KIS API Manager 초기화 실패: {e}")
            return False
    
    def _initialize_auth(self) -> bool:
        """KIS 인증 초기화"""
        try:
            # 토큰 발급/갱신
            if kis_auth.auth():
                self.is_authenticated = True
                self.last_auth_time = now_kst()
                self.logger.info("✅ KIS 인증 성공")
                return True
            else:
                self.logger.error("❌ KIS 인증 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ KIS 인증 초기화 오류: {e}")
            return False
    
    def _validate_settings(self) -> bool:
        """설정 검증"""
        try:
            # 환경 설정 확인
            env = kis_auth.getTREnv()
            if not env:
                self.logger.error("❌ KIS 환경 설정이 없습니다")
                return False
            
            # 필수 설정값 확인
            if not env.my_app or not env.my_sec or not env.my_acct:
                self.logger.error("❌ KIS API 필수 설정값이 누락되었습니다")
                return False
            
            self.logger.info("✅ KIS 설정 검증 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ KIS 설정 검증 오류: {e}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """인증 상태 확인 및 재인증"""
        if not self.is_authenticated:
            return self._initialize_auth()
        
        # 토큰 만료 확인 (1시간마다 재인증)
        if self.last_auth_time and (now_kst() - self.last_auth_time).total_seconds() > 3600:
            self.logger.info("토큰 만료 예정, 재인증 시도...")
            return self._initialize_auth()
        
        return True
    
    def _call_api_with_retry(self, api_func, *args, **kwargs) -> Any:
        """API 호출 with 재시도 로직"""
        self.call_count += 1
        
        for attempt in range(self.max_retries):
            try:
                # 인증 상태 확인
                if not self._ensure_authenticated():
                    raise Exception("인증 실패")
                
                # API 호출 속도 제한
                self._rate_limit()
                
                # 실제 API 호출
                result = api_func(*args, **kwargs)
                
                # 성공 시 결과 반환
                if result is not None:
                    return result
                
                # 결과가 None인 경우 재시도
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                
                return None
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"API 호출 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                
                raise e
        
        return None
    
    def _rate_limit(self):
        """API 호출 속도 제한"""
        current_time = time.time()
        time_diff = current_time - self.last_call_time
        
        # 최소 간격 (60ms) 보장
        if time_diff < 0.06:
            time.sleep(0.06 - time_diff)
        
        self.last_call_time = time.time()
    
    # ===========================================
    # 계좌 조회 API
    # ===========================================
    
    def get_account_balance(self) -> Optional[AccountInfo]:
        """계좌 잔고 조회"""
        try:
            # 계좌 요약 정보 조회
            balance_obj = self._call_api_with_retry(kis_account_api.get_inquire_balance_obj)
            if balance_obj is None or balance_obj.empty:
                return None
            
            # 보유 종목 리스트 조회 (이제 List[Dict] 반환)
            holdings = self._call_api_with_retry(kis_market_api.get_existing_holdings)
            if holdings is None:
                holdings = []
            
            # 데이터 파싱
            balance_data = balance_obj.iloc[0] if not balance_obj.empty else {}
            
            account_info = AccountInfo(
                account_balance=float(balance_data.get('nass_amt', 0)),  # 순자산
                available_amount=float(balance_data.get('nxdy_excc_amt', 0)),  # 매수가능금액
                stock_value=float(balance_data.get('scts_evlu_amt', 0)),  # 보유주식평가액
                total_value=float(balance_data.get('tot_evlu_amt', 0)),  # 총평가액
                positions=cast(List[Dict[str, Any]], holdings)  # 이미 List[Dict] 형태
            )
            
            return account_info
            
        except Exception as e:
            self.logger.error(f"계좌 잔고 조회 실패: {e}")
            return None
    
    def get_account_balance_quick(self) -> Optional[AccountInfo]:
        """계좌 잔고만 빠르게 조회 (보유 종목 제외)"""
        try:
            # 계좌 요약 정보만 조회 (보유 종목 리스트 제외로 빠른 조회)
            balance_obj = self._call_api_with_retry(kis_account_api.get_inquire_balance_obj)
            if balance_obj is None or balance_obj.empty:
                return None
            
            # 데이터 파싱
            balance_data = balance_obj.iloc[0] if not balance_obj.empty else {}
            
            # 가용금액 계산: 예수금총금액 + 익일정산금액 + 가수도정산금액
            dnca_tot_amt = float(balance_data.get('dnca_tot_amt', 0))  # 예수금총금액
            nxdy_excc_amt = float(balance_data.get('nxdy_excc_amt', 0))  # 익일정산금액
            prvs_rcdl_excc_amt = float(balance_data.get('prvs_rcdl_excc_amt', 0))  # 가수도정산금액
            
            available_amount = nxdy_excc_amt
            
            account_info = AccountInfo(
                account_balance=float(balance_data.get('nass_amt', 0)),  # 순자산
                available_amount=available_amount,  # 매수가능금액 (3개 합계)
                stock_value=float(balance_data.get('scts_evlu_amt', 0)),  # 보유주식평가액
                total_value=float(balance_data.get('tot_evlu_amt', 0)),  # 총평가액
                positions=[]  # 보유 종목 정보는 제외 (빠른 조회용)
            )
            
            self.logger.debug(f"💰 계좌 잔고 빠른 조회: 예수금 {dnca_tot_amt:,.0f}원 + 익일정산 {nxdy_excc_amt:,.0f}원 + 가수도정산 {prvs_rcdl_excc_amt:,.0f}원 = 가용금액 {available_amount:,.0f}원")
            
            return account_info
            
        except Exception as e:
            self.logger.error(f"계좌 잔고 빠른 조회 실패: {e}")
            return None
    
    def get_tradable_amount(self, stock_code: str, price: float) -> Optional[int]:
        """매수 가능 수량 조회"""
        try:
            result = self._call_api_with_retry(
                kis_account_api.get_inquire_psbl_order,
                stock_code, int(price)
            )
            
            if result is None or result.empty:
                return None
            
            data = result.iloc[0]
            max_qty = int(data.get('ord_psbl_qty', 0))
            
            return max_qty
            
        except Exception as e:
            self.logger.error(f"매수가능수량 조회 실패 {stock_code}: {e}")
            return None
    
    # ===========================================
    # 시장 데이터 조회 API
    # ===========================================
    
    def get_current_price(self, stock_code: str) -> Optional[StockPrice]:
        """현재가 조회"""
        
        try:
            result = self._call_api_with_retry(
                kis_market_api.get_inquire_price,
                "J", stock_code
            )
            
            if result is None or result.empty:
                return None
            
            data = result.iloc[0]
            
            stock_price = StockPrice(
                stock_code=stock_code,
                current_price=float(data.get('stck_prpr', 0)),
                change_amount=float(data.get('prdy_vrss', 0)),
                change_rate=float(data.get('prdy_ctrt', 0)),
                volume=int(data.get('acml_vol', 0)),
                timestamp=now_kst()
            )
            
            return stock_price
            
        except Exception as e:
            self.logger.error(f"현재가 조회 실패 {stock_code}: {e}")
            return None
    
    def get_current_prices(self, stock_codes: List[str]) -> Dict[str, StockPrice]:
        """여러 종목 현재가 조회"""
        prices = {}
        
        for stock_code in stock_codes:
            price = self.get_current_price(stock_code)
            if price:
                prices[stock_code] = price
            
            # API 호출 간격 조절
            time.sleep(0.1)
        
        return prices
    
    def get_ohlcv_data(self, stock_code: str, period: str = "D", days: int = 30) -> Optional[pd.DataFrame]:
        """OHLCV 데이터 조회"""
        try:
            end_date = now_kst().strftime("%Y%m%d")
            start_date = (now_kst() - timedelta(days=days)).strftime("%Y%m%d")
            
            result = self._call_api_with_retry(
                kis_market_api.get_inquire_daily_itemchartprice,
                "2", "J", stock_code, start_date, end_date, period
            )
            
            if result is None or result.empty:
                return None
            
            # 데이터 정제
            df = result.copy()
            df['stck_bsop_date'] = pd.to_datetime(df['stck_bsop_date'])
            df = df.sort_values('stck_bsop_date')
            
            return df
            
        except Exception as e:
            self.logger.error(f"OHLCV 데이터 조회 실패 {stock_code}: {e}")
            return None
    
    def get_index_data(self, index_code: str = "0001") -> Optional[Dict[str, Any]]:
        """지수 데이터 조회"""
        try:
            result = self._call_api_with_retry(
                kis_market_api.get_index_data,
                index_code
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"지수 데이터 조회 실패 {index_code}: {e}")
            return None
    
    def get_investor_flow_data(self) -> Optional[Dict[str, Any]]:
        """투자자별 매매동향 조회"""
        try:
            result = self._call_api_with_retry(kis_market_api.get_investor_flow_data)
            return result
            
        except Exception as e:
            self.logger.error(f"투자자별 매매동향 조회 실패: {e}")
            return None
    
    # ===========================================
    # 주문 관련 API
    # ===========================================
    
    def place_buy_order(self, stock_code: str, quantity: int, price: int) -> OrderResult:
        """매수 주문"""
        try:
            result = self._call_api_with_retry(
                kis_order_api.get_order_cash,
                "buy", stock_code, quantity, price
            )
            
            if result is None or result.empty:
                return OrderResult(
                    success=False,
                    message="주문 실패 - 응답 없음"
                )
            
            data = result.iloc[0]
            order_id = data.get('ODNO', '')
            
            if order_id:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    message="매수 주문 성공",
                    data=data.to_dict()
                )
            else:
                return OrderResult(
                    success=False,
                    message="주문 실패 - 주문번호 없음",
                    data=data.to_dict()
                )
                
        except Exception as e:
            self.logger.error(f"매수 주문 실패 {stock_code}: {e}")
            return OrderResult(
                success=False,
                message=f"매수 주문 오류: {e}"
            )
    
    def place_sell_order(self, stock_code: str, quantity: int, price: int) -> OrderResult:
        """매도 주문"""
        try:
            result = self._call_api_with_retry(
                kis_order_api.get_order_cash,
                "sell", stock_code, quantity, price
            )
            
            if result is None or result.empty:
                return OrderResult(
                    success=False,
                    message="주문 실패 - 응답 없음"
                )
            
            data = result.iloc[0]
            order_id = data.get('ODNO', '')
            
            if order_id:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    message="매도 주문 성공",
                    data=data.to_dict()
                )
            else:
                return OrderResult(
                    success=False,
                    message="주문 실패 - 주문번호 없음",
                    data=data.to_dict()
                )
                
        except Exception as e:
            self.logger.error(f"매도 주문 실패 {stock_code}: {e}")
            return OrderResult(
                success=False,
                message=f"매도 주문 오류: {e}"
            )
    
    def cancel_order(self, order_id: str, stock_code: str, order_type: str = "00") -> OrderResult:
        """주문 취소"""
        try:
            from utils.korean_time import is_before_market_open, now_kst
            
            # 🔥 장 시작 전에는 주문 취소가 불가능함을 먼저 확인
            if is_before_market_open(now_kst()):
                return OrderResult(
                    success=False,
                    message="장 시작 전에는 주문 취소가 불가능합니다"
                )
            
            # 취소 가능한 주문 조회
            pending_orders = self._call_api_with_retry(
                kis_order_api.get_inquire_psbl_rvsecncl_lst
            )
            
            if pending_orders is None or pending_orders.empty:
                # 🔥 추가 확인: 혹시 이미 체결되었는지 확인
                order_status = self.get_order_status(order_id)
                if order_status:
                    filled_qty = int(order_status.get('tot_ccld_qty', 0))
                    order_qty = int(order_status.get('ord_qty', 0))
                    if filled_qty > 0 and filled_qty == order_qty:
                        return OrderResult(
                            success=False,
                            message="주문이 이미 완전 체결되어 취소할 수 없습니다"
                        )
                
                return OrderResult(
                    success=False,
                    message="취소 가능한 주문 없음"
                )
            
            # 해당 주문 찾기
            target_order = pending_orders[pending_orders['odno'] == order_id]
            if target_order.empty:
                # 🔥 추가 확인: 혹시 이미 체결되었는지 확인
                order_status = self.get_order_status(order_id)
                if order_status:
                    filled_qty = int(order_status.get('tot_ccld_qty', 0))
                    order_qty = int(order_status.get('ord_qty', 0))
                    if filled_qty > 0 and filled_qty == order_qty:
                        return OrderResult(
                            success=False,
                            message="주문이 이미 완전 체결되어 취소할 수 없습니다"
                        )
                
                return OrderResult(
                    success=False,
                    message="취소 대상 주문을 찾을 수 없음 (이미 체결되었을 가능성)"
                )
            
            order_data = target_order.iloc[0]
            
            # 주문 취소 실행
            result = self._call_api_with_retry(
                kis_order_api.get_order_rvsecncl,
                order_data['orgn_odno'],  # 원주문번호
                order_data['odno'],       # 주문번호
                order_type,               # 주문구분
                "02",                     # 취소구분
                0,                        # 수량 (취소시 0)
                0,                        # 가격 (취소시 0)
                "Y"                       # 전량취소
            )
            
            if result is None or result.empty:
                return OrderResult(
                    success=False,
                    message="주문 취소 API 호출 실패"
                )
            
            # 🔥 취소 결과 상세 확인
            cancel_result = result.iloc[0]
            rt_cd = cancel_result.get('rt_cd', '')
            msg1 = cancel_result.get('msg1', '')
            
            if rt_cd == '0':  # 성공
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    message="주문 취소 성공",
                    data=cancel_result.to_dict()
                )
            else:
                return OrderResult(
                    success=False,
                    message=f"주문 취소 실패: {msg1}",
                    error_code=rt_cd,
                    data=cancel_result.to_dict()
                )
            
        except Exception as e:
            self.logger.error(f"주문 취소 실패 {order_id}: {e}")
            return OrderResult(
                success=False,
                message=f"주문 취소 오류: {e}"
            )
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """주문 상태 조회 - 미체결 주문 조회 + 체결 내역 조회 조합"""
        try:
            # 1. 미체결 주문 조회 (정정취소 가능 주문)
            pending_orders = self._call_api_with_retry(
                kis_order_api.get_inquire_psbl_rvsecncl_lst
            )
            
            # 2. 미체결 주문 목록에서 해당 주문 찾기
            is_pending = False
            pending_order_data = None
            
            if pending_orders is not None and not pending_orders.empty:
                target_pending = pending_orders[pending_orders['odno'] == order_id]
                if not target_pending.empty:
                    is_pending = True
                    pending_order_data = target_pending.iloc[0].to_dict()
            
            # 3. 체결 내역 조회 (완전 체결 확인 및 상세 정보용)
            daily_results = self._call_api_with_retry(
                kis_order_api.get_inquire_daily_ccld_lst,
                "01"  # 3개월 이내
            )
            
            # 4. 해당 주문의 모든 체결 레코드 찾기
            all_filled_records = None
            if daily_results is not None and not daily_results.empty:
                all_filled_records = daily_results[daily_results['odno'] == order_id]
            
            # 5. 주문 상태 결정 및 데이터 생성
            if is_pending and pending_order_data:
                # 🔄 미체결 주문이 존재 = 부분 체결 또는 미체결
                order_data = pending_order_data.copy()
                
                # 체결량 정보 추가 (미체결 주문에는 원주문수량과 잔여수량이 있음)
                total_order_qty = int(order_data.get('ord_qty', 0))      # 원주문수량
                remaining_qty = int(order_data.get('rmn_qty', 0))        # 잔여수량  
                filled_qty = total_order_qty - remaining_qty             # 체결수량 = 원주문수량 - 잔여수량
                
                order_data['tot_ccld_qty'] = str(filled_qty)             # 총체결수량
                order_data['rmn_qty'] = str(remaining_qty)               # 잔여수량
                order_data['ord_qty'] = str(total_order_qty)             # 주문수량
                order_data['cncl_yn'] = 'N'                              # 취소여부
                
                self.logger.info(f"🔄 부분 체결 확인: {order_id} - 체결: {filled_qty}/{total_order_qty}")
                
            elif all_filled_records is not None and not all_filled_records.empty:
                # ✅ 미체결 주문 목록에 없고 체결 내역 존재 = 완전 체결
                
                # 🔧 수정: 체결 수량 계산 로직 개선
                total_filled_qty = 0
                order_qty = 0
                last_record = None
                
                for _, record in all_filled_records.iterrows():
                    # 🔧 수정: 체결량 필드명 확인 및 안전한 변환
                    ccld_qty_str = str(record.get('ccld_qty', '0')).strip()
                    ord_qty_str = str(record.get('ord_qty', '0')).strip()
                    
                    # 빈 문자열이나 '-' 처리
                    if ccld_qty_str in ['', '-', 'None']:
                        ccld_qty_str = '0'
                    if ord_qty_str in ['', '-', 'None']:
                        ord_qty_str = '0'
                    
                    try:
                        ccld_qty = int(float(ccld_qty_str))  # float로 먼저 변환 후 int
                        ord_qty = int(float(ord_qty_str))
                    except (ValueError, TypeError):
                        self.logger.warning(f"⚠️ 체결량 변환 실패: ccld_qty={ccld_qty_str}, ord_qty={ord_qty_str}")
                        ccld_qty = 0
                        ord_qty = 0
                    
                    total_filled_qty += ccld_qty
                    if ord_qty > 0:  # 주문수량이 유효한 경우에만 업데이트
                        order_qty = ord_qty
                    last_record = record
                
                # 🔧 수정: 체결 수량이 0인 경우 대체 로직
                if total_filled_qty == 0 and order_qty > 0:
                    # 체결 내역이 있지만 체결량이 0인 경우, 주문수량을 체결량으로 간주
                    # (완전 체결된 주문이 체결 내역에 있다면 체결되었다고 판단)
                    total_filled_qty = order_qty
                    self.logger.info(f"🔧 체결량 보정: {order_id} - 체결내역 존재하므로 {order_qty}주 완전체결로 간주")
                
                if last_record is not None:
                    order_data = last_record.to_dict()
                    order_data['tot_ccld_qty'] = str(total_filled_qty)   # 총체결수량 (수정된 값)
                    order_data['rmn_qty'] = str(max(0, order_qty - total_filled_qty))  # 잔여수량
                    order_data['ord_qty'] = str(order_qty)              # 주문수량
                    order_data['cncl_yn'] = 'N'                         # 취소여부
                    
                    self.logger.info(f"✅ 완전 체결 확인: {order_id} - 체결: {total_filled_qty}/{order_qty} (레코드 {len(all_filled_records)}개)")
                else:
                    return None
            else:
                # ❌ 미체결 주문도 없고 체결 내역도 없음 = 주문 취소 또는 오류
                self.logger.warning(f"⚠️ 주문 상태 불명: {order_id}")
                return None
            
            return order_data
            
        except Exception as e:
            self.logger.info(f"주문 상태 조회 실패 {order_id}: {e}")
            return None
    
    # ===========================================
    # 유틸리티 함수들
    # ===========================================
    
    def get_api_statistics(self) -> Dict[str, Any]:
        """API 호출 통계"""
        return {
            'total_calls': self.call_count,
            'error_count': self.error_count,
            'success_rate': (self.call_count - self.error_count) / max(self.call_count, 1) * 100,
            'is_authenticated': self.is_authenticated,
            'last_auth_time': self.last_auth_time.isoformat() if self.last_auth_time else None
        }
    

    def health_check(self) -> bool:
        """API 상태 확인"""
        try:
            # 간단한 API 호출로 상태 확인
            result = self.get_current_price("005930")  # 삼성전자
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Health check 실패: {e}")
            return False
    
    def shutdown(self):
        """API 매니저 종료"""
        self.logger.info("KIS API Manager 종료 중...")
        self.is_initialized = False
        self.is_authenticated = False
        self.logger.info("KIS API Manager 종료 완료") 