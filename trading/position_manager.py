"""
포지션 관리 클래스

기존 포지션 로드, 포지션 업데이트, 포지션 분석 등을 담당합니다.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import queue

from api.kis_api_manager import KISAPIManager, AccountInfo
from core.models import Position, TradingConfig
from core.enums import PositionStatus, OrderType
from utils.logger import setup_logger
from utils.korean_time import now_kst


class PositionManager:
    """포지션 관리 클래스"""
    
    def __init__(self, api_manager: KISAPIManager, config: TradingConfig, message_queue: queue.Queue):
        """
        포지션 관리자 초기화
        
        Args:
            api_manager: KIS API 매니저
            config: 매매 설정
            message_queue: 메시지 큐
        """
        self.logger = setup_logger(__name__)
        self.api_manager = api_manager
        self.config = config
        self.message_queue = message_queue
        
        # 포지션 통계
        self.position_stats = {
            'total_positions': 0,
            'profitable_positions': 0,
            'losing_positions': 0,
            'total_value': 0.0,
            'total_profit_loss': 0.0,
            'last_update': None
        }
        
        self.logger.info("✅ PositionManager 초기화 완료")
    
    def load_existing_positions(self, account_info: AccountInfo) -> Dict[str, Position]:
        """
        기존 포지션 로드
        
        Args:
            account_info: 계좌 정보
            
        Returns:
            Dict[str, Position]: 포지션 딕셔너리
        """
        try:
            positions = {}
            
            if not account_info or not account_info.positions:
                self.logger.info("📋 기존 포지션 없음")
                return positions
            
            loaded_count = 0
            for pos_data in account_info.positions:
                position = self._create_position_from_data(pos_data)
                if position:
                    positions[position.stock_code] = position
                    loaded_count += 1
            
            self.logger.info(f"📋 기존 포지션 로드 완료: {loaded_count}개")
            
            # 포지션 통계 업데이트
            self._update_position_stats(positions)
            
            # 포지션 요약 로그
            self._log_position_summary(positions)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"❌ 기존 포지션 로드 오류: {e}")
            return {}
    
    def update_positions(self, positions: Dict[str, Position]) -> None:
        """
        포지션 정보 업데이트
        
        Args:
            positions: 업데이트할 포지션들
        """
        try:
            updated_count = 0
            
            for stock_code, position in positions.items():
                if self._update_single_position(position):
                    updated_count += 1
            
            if updated_count > 0:
                self.logger.debug(f"📊 포지션 업데이트 완료: {updated_count}개")
                
                # 포지션 통계 업데이트
                self._update_position_stats(positions)
                
        except Exception as e:
            self.logger.error(f"❌ 포지션 업데이트 오류: {e}")
    
    def update_position_after_trade(self, positions: Dict[str, Position], stock_code: str, 
                                   trade_type: str, quantity: int, price: float,
                                   stop_loss_price: Optional[float] = None,
                                   take_profit_price: Optional[float] = None) -> None:
        """
        거래 후 포지션 업데이트
        
        Args:
            positions: 포지션 딕셔너리
            stock_code: 종목 코드
            trade_type: 거래 타입 ("BUY" or "SELL")
            quantity: 거래 수량
            price: 거래 가격
            stop_loss_price: 손절가 (매수 시만 사용)
            take_profit_price: 익절가 (매수 시만 사용)
        """
        try:
            if trade_type == "BUY":
                self._add_position(positions, stock_code, quantity, price, stop_loss_price, take_profit_price)
            elif trade_type == "SELL":
                self._reduce_position(positions, stock_code, quantity)
                
        except Exception as e:
            self.logger.error(f"❌ 거래 후 포지션 업데이트 오류: {e}")
    
    def analyze_positions(self, positions: Dict[str, Position]) -> Dict[str, Any]:
        """
        포지션 분석
        
        Args:
            positions: 분석할 포지션들
            
        Returns:
            Dict[str, Any]: 분석 결과
        """
        try:
            if not positions:
                return {
                    'total_positions': 0,
                    'total_value': 0.0,
                    'total_profit_loss': 0.0,
                    'profit_loss_rate': 0.0,
                    'profitable_count': 0,
                    'losing_count': 0,
                    'largest_position': None,
                    'most_profitable': None,
                    'most_losing': None,
                    'sector_distribution': {},
                    'risk_analysis': {}
                }
            
            analysis = {
                'total_positions': len(positions),
                'total_value': 0.0,
                'total_profit_loss': 0.0,
                'profitable_count': 0,
                'losing_count': 0,
                'positions_detail': []
            }
            
            largest_value = 0.0
            largest_position = None
            most_profitable = None
            most_losing = None
            max_profit = float('-inf')
            max_loss = float('inf')
            
            for position in positions.values():
                # 기본 통계
                position_value = position.quantity * position.current_price
                analysis['total_value'] += position_value
                analysis['total_profit_loss'] += position.profit_loss
                
                # 수익/손실 포지션 카운트
                if position.profit_loss > 0:
                    analysis['profitable_count'] += 1
                elif position.profit_loss < 0:
                    analysis['losing_count'] += 1
                
                # 최대 포지션 찾기
                if position_value > largest_value:
                    largest_value = position_value
                    largest_position = position
                
                # 최대 수익/손실 포지션 찾기
                if position.profit_loss > max_profit:
                    max_profit = position.profit_loss
                    most_profitable = position
                
                if position.profit_loss < max_loss:
                    max_loss = position.profit_loss
                    most_losing = position
                
                # 포지션 상세 정보
                analysis['positions_detail'].append({
                    'stock_code': position.stock_code,
                    'stock_name': position.stock_name,
                    'quantity': position.quantity,
                    'avg_price': position.avg_price,
                    'current_price': position.current_price,
                    'value': position_value,
                    'profit_loss': position.profit_loss,
                    'profit_loss_rate': position.profit_loss_rate,
                    'weight': position_value / analysis['total_value'] if analysis['total_value'] > 0 else 0
                })
            
            # 수익률 계산
            if analysis['total_value'] > 0:
                total_cost = analysis['total_value'] - analysis['total_profit_loss']
                analysis['profit_loss_rate'] = (analysis['total_profit_loss'] / total_cost * 100) if total_cost > 0 else 0.0
            else:
                analysis['profit_loss_rate'] = 0.0
            
            # 추가 분석 정보
            analysis['largest_position'] = largest_position.__dict__ if largest_position else None
            analysis['most_profitable'] = most_profitable.__dict__ if most_profitable else None
            analysis['most_losing'] = most_losing.__dict__ if most_losing else None
            
            # 리스크 분석
            analysis['risk_analysis'] = self._analyze_risk(positions, analysis['total_value'])
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 분석 오류: {e}")
            return {}
    
    def get_positions_requiring_attention(self, positions: Dict[str, Position]) -> List[Position]:
        """
        주의가 필요한 포지션 찾기
        
        Args:
            positions: 검사할 포지션들
            
        Returns:
            List[Position]: 주의가 필요한 포지션들
        """
        try:
            attention_positions = []
            
            for position in positions.values():
                # 손절 조건 확인
                if position.profit_loss_rate <= self.config.stop_loss_ratio * 100:
                    attention_positions.append(position)
                    self.logger.warning(f"⚠️ 손절 조건: {position.stock_name} ({position.profit_loss_rate:.2f}%)")
                
                # 익절 조건 확인
                elif position.profit_loss_rate >= self.config.take_profit_ratio * 100:
                    attention_positions.append(position)
                    self.logger.info(f"✅ 익절 조건: {position.stock_name} ({position.profit_loss_rate:.2f}%)")
            
            return attention_positions
            
        except Exception as e:
            self.logger.error(f"❌ 주의 포지션 검사 오류: {e}")
            return []
    
    def _create_position_from_data(self, pos_data: Dict[str, Any]) -> Optional[Position]:
        """계좌 데이터로부터 포지션 생성"""
        try:
            stock_code = pos_data.get('pdno', '')
            stock_name = pos_data.get('prdt_name', '')
            quantity = int(pos_data.get('hldg_qty', 0))
            avg_price = float(pos_data.get('pchs_avg_pric', 0))
            current_price = float(pos_data.get('prpr', 0))
            profit_loss = float(pos_data.get('evlu_pfls_amt', 0))
            profit_loss_rate = float(pos_data.get('evlu_pfls_rt', 0))
            
            if quantity > 0 and stock_code:
                position = Position(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    quantity=quantity,
                    avg_price=avg_price,
                    current_price=current_price,
                    profit_loss=profit_loss,
                    profit_loss_rate=profit_loss_rate,
                    entry_time=now_kst(),  # 정확한 진입 시간은 별도 관리 필요
                    last_update=now_kst(),
                    status=PositionStatus.ACTIVE,
                    order_type=OrderType.LIMIT
                )
                
                return position
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 생성 오류: {e}")
            return None
    
    def _update_single_position(self, position: Position) -> bool:
        """단일 포지션 업데이트"""
        try:
            current_price_info = self.api_manager.get_current_price(position.stock_code)
            
            if current_price_info:
                position.current_price = current_price_info.current_price
                position.profit_loss = (position.current_price - position.avg_price) * position.quantity
                position.profit_loss_rate = (position.current_price - position.avg_price) / position.avg_price * 100
                position.last_update = now_kst()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 단일 포지션 업데이트 오류 {position.stock_code}: {e}")
            return False
    
    def _add_position(self, positions: Dict[str, Position], stock_code: str, 
                     quantity: int, price: float,
                     stop_loss_price: Optional[float] = None,
                     take_profit_price: Optional[float] = None) -> None:
        """포지션 추가 (매수)"""
        try:
            if stock_code in positions:
                # 기존 포지션 평균가 계산
                position = positions[stock_code]
                total_quantity = position.quantity + quantity
                total_amount = (position.avg_price * position.quantity) + (price * quantity)
                new_avg_price = total_amount / total_quantity
                
                position.quantity = total_quantity
                position.avg_price = new_avg_price
                position.last_update = now_kst()
                
                # 손절/익절가 업데이트 (새로운 값이 있는 경우)
                if stop_loss_price is not None:
                    position.stop_loss_price = stop_loss_price
                if take_profit_price is not None:
                    position.take_profit_price = take_profit_price
                
                self.logger.debug(f"📊 포지션 추가: {stock_code} {quantity}주 @ {price:,.0f}원")
            else:
                # 새 포지션 생성
                stock_name = f"종목{stock_code}"  # 실제로는 API에서 종목명 조회 필요
                
                new_position = Position(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    quantity=quantity,
                    avg_price=price,
                    current_price=price,
                    profit_loss=0.0,
                    profit_loss_rate=0.0,
                    entry_time=now_kst(),
                    last_update=now_kst(),
                    status=PositionStatus.ACTIVE,
                    order_type=OrderType.LIMIT,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                    entry_reason="패턴 기반 매수"
                )
                
                positions[stock_code] = new_position
                self.logger.info(f"📊 새 포지션 생성: {stock_code} {quantity}주 @ {price:,.0f}원")
                
        except Exception as e:
            self.logger.error(f"❌ 포지션 추가 오류: {e}")
    
    def _reduce_position(self, positions: Dict[str, Position], stock_code: str, quantity: int) -> None:
        """포지션 감소 (매도)"""
        try:
            if stock_code in positions:
                position = positions[stock_code]
                position.quantity -= quantity
                position.last_update = now_kst()
                
                if position.quantity <= 0:
                    position.status = PositionStatus.CLOSED
                    self.logger.debug(f"📊 포지션 완전 매도: {stock_code}")
                else:
                    self.logger.debug(f"📊 포지션 부분 매도: {stock_code} {quantity}주")
                    
        except Exception as e:
            self.logger.error(f"❌ 포지션 감소 오류: {e}")
    
    def _update_position_stats(self, positions: Dict[str, Position]) -> None:
        """포지션 통계 업데이트"""
        try:
            self.position_stats['total_positions'] = len(positions)
            self.position_stats['profitable_positions'] = sum(1 for p in positions.values() if p.profit_loss > 0)
            self.position_stats['losing_positions'] = sum(1 for p in positions.values() if p.profit_loss < 0)
            self.position_stats['total_value'] = sum(p.quantity * p.current_price for p in positions.values())
            self.position_stats['total_profit_loss'] = sum(p.profit_loss for p in positions.values())
            self.position_stats['last_update'] = now_kst()
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 통계 업데이트 오류: {e}")
    
    def _log_position_summary(self, positions: Dict[str, Position]) -> None:
        """포지션 요약 로그"""
        try:
            if not positions:
                return
            
            total_value = sum(p.quantity * p.current_price for p in positions.values())
            total_profit_loss = sum(p.profit_loss for p in positions.values())
            profitable_count = sum(1 for p in positions.values() if p.profit_loss > 0)
            
            self.logger.info(f"📊 포지션 요약: {len(positions)}개 종목, "
                           f"총 {total_value:,.0f}원, 손익 {total_profit_loss:+,.0f}원, "
                           f"수익 {profitable_count}개")
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 요약 로그 오류: {e}")
    
    def _analyze_risk(self, positions: Dict[str, Position], total_value: float) -> Dict[str, Any]:
        """리스크 분석"""
        try:
            risk_analysis = {
                'concentration_risk': 0.0,
                'largest_position_weight': 0.0,
                'positions_over_limit': 0,
                'total_exposure': 0.0
            }
            
            if not positions or total_value <= 0:
                return risk_analysis
            
            # 집중도 리스크 계산
            weights = []
            for position in positions.values():
                position_value = position.quantity * position.current_price
                weight = position_value / total_value
                weights.append(weight)
                
                # 최대 포지션 비중
                if weight > risk_analysis['largest_position_weight']:
                    risk_analysis['largest_position_weight'] = weight
                
                # 한도 초과 포지션 수
                if weight > self.config.max_position_ratio:
                    risk_analysis['positions_over_limit'] += 1
            
            # 집중도 리스크 (허핀달 지수)
            risk_analysis['concentration_risk'] = sum(w ** 2 for w in weights)
            risk_analysis['total_exposure'] = sum(weights)
            
            return risk_analysis
            
        except Exception as e:
            self.logger.error(f"❌ 리스크 분석 오류: {e}")
            return {}
    
    def get_position_stats(self) -> Dict[str, Any]:
        """포지션 통계 반환"""
        return self.position_stats.copy() 