"""
데이터베이스 관리 클래스

SQLite 데이터베이스 연결 및 기본 CRUD 작업을 담당합니다.
"""
import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from utils.logger import setup_logger
from utils.korean_time import now_kst, ensure_kst
from core.models import Position, TradeRecord, AccountSnapshot
from core.enums import PositionStatus, OrderType, PatternType
from trading.candidate_screener import PatternResult
from core.enums import PatternType
from trading.technical_analyzer import MarketCapType


class DatabaseManager:
    """데이터베이스 매니저"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        """
        데이터베이스 매니저 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.logger = setup_logger(__name__)
        self.connection: Optional[sqlite3.Connection] = None
        
        # 데이터베이스 초기화
        self.initialize_database()
    
    def _ensure_connection(self) -> bool:
        """
        데이터베이스 연결 확인 및 재연결
        
        Returns:
            bool: 연결 성공 여부
        """
        if self.connection is None:
            return self.initialize_database()
        return True
    
    def _get_cursor(self) -> Optional[sqlite3.Cursor]:
        """
        데이터베이스 커서 반환 (연결 확인 포함)
        
        Returns:
            Optional[sqlite3.Cursor]: 커서 객체 또는 None
        """
        if not self._ensure_connection() or self.connection is None:
            return None
        return self.connection.cursor()
    
    def _commit(self) -> bool:
        """
        트랜잭션 커밋
        
        Returns:
            bool: 커밋 성공 여부
        """
        if self.connection is None:
            return False
        try:
            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"❌ 커밋 실패: {e}")
            return False
    
    def _rollback(self) -> bool:
        """
        트랜잭션 롤백
        
        Returns:
            bool: 롤백 성공 여부
        """
        if self.connection is None:
            return False
        try:
            self.connection.rollback()
            return True
        except Exception as e:
            self.logger.error(f"❌ 롤백 실패: {e}")
            return False
    
    def initialize_database(self) -> bool:
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            
            # 테이블 생성
            self._create_tables()
            
            self.logger.info("✅ 데이터베이스 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
            self.connection = None
            return False
    
    def _create_tables(self) -> None:
        """테이블 생성"""
        cursor = self._get_cursor()
        if cursor is None:
            return
        
        # 기존 테이블 스키마 업그레이드 (하위 호환성)
        self._upgrade_schema(cursor)
        
        # 후보종목 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_strength REAL NOT NULL,
                current_price REAL NOT NULL,
                target_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                market_cap_type TEXT NOT NULL,
                volume_ratio REAL NOT NULL,
                technical_score REAL NOT NULL,
                pattern_date TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                screening_date DATE NOT NULL
            )
        """)
        
        # 포지션 테이블 (현재 보유 종목)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL UNIQUE,
                stock_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL NOT NULL,
                profit_loss REAL NOT NULL,
                profit_loss_rate REAL NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                last_update TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                order_type TEXT NOT NULL DEFAULT 'LIMIT',
                stop_loss_price REAL,
                take_profit_price REAL,
                entry_reason TEXT NOT NULL DEFAULT '',
                notes TEXT DEFAULT '',
                target_price REAL,
                original_candidate_id INTEGER, 
                partial_sold BOOLEAN DEFAULT 0, 
                pattern_type TEXT, market_cap_type TEXT, 
                pattern_strength REAL, volume_ratio REAL,
                partial_exit_stage INTEGER DEFAULT 0,
                partial_exit_ratio REAL DEFAULT 0.0,
                last_partial_exit_date TIMESTAMP,
                partial_exit_history TEXT DEFAULT '[]',
                FOREIGN KEY (original_candidate_id) REFERENCES candidate_stocks(id)
            )
        """)
        
        # 거래 기록 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                trade_type TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                reason TEXT NOT NULL,
                order_id TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                message TEXT NOT NULL,
                commission REAL DEFAULT 0.0,
                tax REAL DEFAULT 0.0,
                net_amount REAL DEFAULT 0.0,
                profit_loss REAL,
                execution_time TIMESTAMP,
                position_id INTEGER,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)
        
        # 계좌 스냅샷 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                total_value REAL NOT NULL,
                available_amount REAL NOT NULL,
                stock_value REAL NOT NULL,
                cash_balance REAL NOT NULL,
                profit_loss REAL NOT NULL,
                profit_loss_rate REAL NOT NULL,
                position_count INTEGER NOT NULL,
                daily_trades INTEGER NOT NULL,
                daily_profit_loss REAL NOT NULL
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_stocks_screening_date ON candidate_stocks(screening_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_stock_code ON positions(stock_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_records_stock_code ON trade_records(stock_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_records_timestamp ON trade_records(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_account_snapshots_timestamp ON account_snapshots(timestamp)")
        
        self._commit()
    
    def _safe_get_pattern_type(self, pattern_type_str: Optional[str]) -> Optional[PatternType]:
        """패턴 타입 문자열을 안전하게 PatternType enum으로 변환"""
        if not pattern_type_str:
            return None
        
        try:
            return PatternType(pattern_type_str)
        except (ValueError, AttributeError):
            # 잘못된 패턴 타입인 경우 None 반환
            self.logger.warning(f"⚠️ 알 수 없는 패턴 타입: {pattern_type_str}")
            return None
    
    def _upgrade_schema(self, cursor) -> None:
        """
        기존 데이터베이스 스키마를 최신 버전으로 업그레이드
        """
        try:
            # positions 테이블에 partial_sold 컬럼이 없으면 추가
            cursor.execute("PRAGMA table_info(positions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # 기존 컬럼들 추가
            if 'partial_sold' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN partial_sold BOOLEAN DEFAULT 0")
                self.logger.info("✅ positions 테이블에 partial_sold 컬럼 추가")
            
            if 'pattern_type' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN pattern_type TEXT")
                self.logger.info("✅ positions 테이블에 pattern_type 컬럼 추가")
            
            if 'market_cap_type' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN market_cap_type TEXT")
                self.logger.info("✅ positions 테이블에 market_cap_type 컬럼 추가")
            
            if 'pattern_strength' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN pattern_strength REAL")
                self.logger.info("✅ positions 테이블에 pattern_strength 컬럼 추가")
            
            if 'volume_ratio' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN volume_ratio REAL")
                self.logger.info("✅ positions 테이블에 volume_ratio 컬럼 추가")
            
            # 🔧 새로운 부분매도 컬럼들 추가
            if 'partial_exit_stage' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN partial_exit_stage INTEGER DEFAULT 0")
                self.logger.info("✅ positions 테이블에 partial_exit_stage 컬럼 추가")
            
            if 'partial_exit_ratio' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN partial_exit_ratio REAL DEFAULT 0.0")
                self.logger.info("✅ positions 테이블에 partial_exit_ratio 컬럼 추가")
            
            if 'last_partial_exit_date' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN last_partial_exit_date TIMESTAMP")
                self.logger.info("✅ positions 테이블에 last_partial_exit_date 컬럼 추가")
            
            if 'partial_exit_history' not in columns:
                cursor.execute("ALTER TABLE positions ADD COLUMN partial_exit_history TEXT DEFAULT '[]'")
                self.logger.info("✅ positions 테이블에 partial_exit_history 컬럼 추가")
            
            self._commit()
            
        except Exception as e:
            self.logger.error(f"❌ 스키마 업그레이드 실패: {e}")
            self._rollback()
    
    def save_candidate_stocks(self, candidates: List[PatternResult], screening_date: str) -> List[int]:
        """
        후보종목 저장
        
        Args:
            candidates: 후보종목 리스트
            screening_date: 스크리닝 날짜 (YYYY-MM-DD)
            
        Returns:
            List[int]: 저장된 후보종목 ID 리스트
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return []
            candidate_ids = []
            
            # 기존 같은 날짜의 후보종목 삭제
            cursor.execute("DELETE FROM candidate_stocks WHERE screening_date = ?", (screening_date,))
            
            # 새 후보종목 저장
            for candidate in candidates:
                cursor.execute("""
                    INSERT INTO candidate_stocks (
                        stock_code, stock_name, pattern_type, pattern_strength,
                        current_price, target_price, stop_loss, market_cap_type,
                        volume_ratio, technical_score, pattern_date, confidence, screening_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    candidate.stock_code,
                    candidate.stock_name,
                    candidate.pattern_type.value,
                    candidate.pattern_strength,
                    candidate.current_price,
                    candidate.target_price,
                    candidate.stop_loss,
                    candidate.market_cap_type.value,
                    candidate.volume_ratio,
                    candidate.technical_score,
                    candidate.pattern_date,
                    candidate.confidence,
                    screening_date,
                    now_kst().strftime('%Y-%m-%d %H:%M:%S')  # 한국시간으로 명시적 설정
                ))
                candidate_ids.append(cursor.lastrowid)
            
            self._commit()
            self.logger.info(f"✅ 후보종목 {len(candidates)}개 저장 완료")
            return candidate_ids
            
        except Exception as e:
            self.logger.error(f"❌ 후보종목 저장 실패: {e}")
            self._rollback()
            return []
    
    def save_position(self, position: Position, candidate_id: Optional[int] = None) -> Optional[int]:
        """
        포지션 저장 (매수 체결 시)
        
        Args:
            position: 포지션 정보
            candidate_id: 원본 후보종목 ID (선택사항)
            
        Returns:
            Optional[int]: 저장된 포지션 ID
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return None
            
            cursor.execute("""
                INSERT OR REPLACE INTO positions (
                    stock_code, stock_name, quantity, avg_price, current_price,
                    profit_loss, profit_loss_rate, entry_time, last_update,
                    status, order_type, stop_loss_price, take_profit_price,
                    entry_reason, notes, original_candidate_id,
                    partial_sold, pattern_type, market_cap_type, pattern_strength, volume_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.stock_code,
                position.stock_name,
                position.quantity,
                position.avg_price,
                position.current_price,
                position.profit_loss,
                position.profit_loss_rate,
                position.entry_time,
                position.last_update,
                position.status.value,
                position.order_type.value,
                position.stop_loss_price,
                position.take_profit_price,
                position.entry_reason,
                position.notes,
                candidate_id,
                position.partial_sold,
                position.pattern_type.value if position.pattern_type else None,
                position.market_cap_type,
                position.pattern_strength,
                position.volume_ratio
            ))
            
            position_id = cursor.lastrowid
            self._commit()
            
            self.logger.info(f"✅ 포지션 저장 완료: {position.stock_name} ({position.stock_code})")
            return position_id
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 저장 실패: {e}")
            self._rollback()
            return None
    
    def update_position(self, position: Position) -> bool:
        """
        포지션 업데이트
        
        Args:
            position: 포지션 정보
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return False
            
            cursor.execute("""
                UPDATE positions SET
                    quantity = ?, avg_price = ?, current_price = ?,
                    profit_loss = ?, profit_loss_rate = ?, last_update = ?,
                    status = ?, stop_loss_price = ?, take_profit_price = ?,
                    notes = ?, partial_sold = ?, pattern_type = ?,
                    market_cap_type = ?, pattern_strength = ?, volume_ratio = ?,
                    partial_exit_stage = ?, partial_exit_ratio = ?, 
                    last_partial_exit_date = ?, partial_exit_history = ?
                WHERE stock_code = ?
            """, (
                position.quantity,
                position.avg_price,
                position.current_price,
                position.profit_loss,
                position.profit_loss_rate,
                position.last_update,
                position.status.value,
                position.stop_loss_price,
                position.take_profit_price,
                position.notes,
                position.partial_sold,
                position.pattern_type.value if position.pattern_type else None,
                position.market_cap_type,
                position.pattern_strength,
                position.volume_ratio,
                # 🔧 새로운 부분매도 필드들
                position.partial_exit_stage,
                position.partial_exit_ratio,
                position.last_partial_exit_date,
                json.dumps(position.partial_exit_history),
                position.stock_code
            ))
            
            self._commit()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 업데이트 실패: {e}")
            self._rollback()
            return False
    
    def remove_position(self, stock_code: str) -> bool:
        """
        포지션 삭제 (매도 체결 시)
        
        Args:
            stock_code: 종목코드
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return False
            
            cursor.execute("DELETE FROM positions WHERE stock_code = ?", (stock_code,))
            self._commit()
            
            self.logger.info(f"✅ 포지션 삭제 완료: {stock_code}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 삭제 실패: {e}")
            self._rollback()
            return False
    
    def save_trade_record(self, trade_record: TradeRecord, position_id: Optional[int] = None) -> Optional[int]:
        """
        거래 기록 저장
        
        Args:
            trade_record: 거래 기록
            position_id: 포지션 ID (선택사항)
            
        Returns:
            Optional[int]: 저장된 거래 기록 ID
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return None
            
            cursor.execute("""
                INSERT INTO trade_records (
                    timestamp, trade_type, stock_code, stock_name, quantity,
                    price, amount, reason, order_id, success, message,
                    commission, tax, net_amount, profit_loss, execution_time, position_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_record.timestamp,
                trade_record.trade_type,
                trade_record.stock_code,
                trade_record.stock_name,
                trade_record.quantity,
                trade_record.price,
                trade_record.amount,
                trade_record.reason,
                trade_record.order_id,
                trade_record.success,
                trade_record.message,
                trade_record.commission,
                trade_record.tax,
                trade_record.net_amount,
                trade_record.profit_loss,
                trade_record.execution_time,
                position_id
            ))
            
            trade_id = cursor.lastrowid
            self._commit()
            
            self.logger.info(f"✅ 거래 기록 저장 완료: {trade_record.trade_type} {trade_record.stock_name}")
            return trade_id
            
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 저장 실패: {e}")
            self._rollback()
            return None
    
    def load_active_positions(self) -> Dict[str, Position]:
        """
        활성 포지션 조회 (프로그램 재시작 시 복원용)
        
        Returns:
            Dict[str, Position]: 종목코드를 키로 하는 포지션 딕셔너리
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return {}
            
            cursor.execute("""
                SELECT * FROM positions 
                WHERE (status = 'ACTIVE' OR status = '활성') AND quantity > 0
                ORDER BY entry_time DESC
            """)
            
            # 상태값 매핑 딕셔너리 (기존 영어 값 -> 한국어 enum 값)
            status_mapping = {
                'ACTIVE': PositionStatus.ACTIVE,
                '활성': PositionStatus.ACTIVE,
                'CLOSED': PositionStatus.CLOSED,
                '종료': PositionStatus.CLOSED,
                'PARTIAL': PositionStatus.PARTIAL,
                '부분체결': PositionStatus.PARTIAL
            }
            
            # 주문타입 매핑 딕셔너리 (기존 영어 값 -> 한국어 enum 값)
            order_type_mapping = {
                'MARKET': OrderType.MARKET,
                '시장가': OrderType.MARKET,
                'LIMIT': OrderType.LIMIT,
                '지정가': OrderType.LIMIT,
                'STOP_LOSS': OrderType.STOP_LOSS,
                '손절': OrderType.STOP_LOSS,
                'TAKE_PROFIT': OrderType.TAKE_PROFIT,
                '익절': OrderType.TAKE_PROFIT
            }
            
            positions = {}
            for row in cursor.fetchall():
                # 상태값 안전하게 변환
                try:
                    status = status_mapping.get(row['status'], PositionStatus.ACTIVE)
                except (ValueError, KeyError):
                    status = PositionStatus.ACTIVE  # 기본값
                
                # 주문타입 안전하게 변환
                try:
                    order_type = order_type_mapping.get(row['order_type'], OrderType.LIMIT)
                except (ValueError, KeyError):
                    order_type = OrderType.LIMIT  # 기본값
                
                # 안전한 컬럼 접근 (컬럼이 없는 경우 기본값 사용)
                def safe_get(column_name, default_value=None):
                    try:
                        return row[column_name]
                    except (KeyError, IndexError):
                        return default_value
                
                position = Position(
                    stock_code=row['stock_code'],
                    stock_name=row['stock_name'],
                    quantity=row['quantity'],
                    avg_price=row['avg_price'],
                    current_price=row['current_price'],
                    profit_loss=row['profit_loss'],
                    profit_loss_rate=row['profit_loss_rate'],
                    entry_time=ensure_kst(datetime.fromisoformat(row['entry_time'])),
                    last_update=ensure_kst(datetime.fromisoformat(row['last_update'])),
                    status=status,
                    order_type=order_type,
                    stop_loss_price=safe_get('stop_loss_price'),
                    take_profit_price=safe_get('take_profit_price'),
                    entry_reason=safe_get('entry_reason', '') or '',
                    notes=safe_get('notes', '') or '',
                    partial_sold=bool(safe_get('partial_sold', False)),
                    pattern_type=self._safe_get_pattern_type(safe_get('pattern_type')),
                    market_cap_type=safe_get('market_cap_type'),
                    pattern_strength=safe_get('pattern_strength'),
                    volume_ratio=safe_get('volume_ratio'),
                    # 🔧 새로운 부분매도 필드들
                    partial_exit_stage=safe_get('partial_exit_stage', 0),
                    partial_exit_ratio=safe_get('partial_exit_ratio', 0.0),
                    last_partial_exit_date=ensure_kst(datetime.fromisoformat(safe_get('last_partial_exit_date'))) if safe_get('last_partial_exit_date') is not None else None,
                    partial_exit_history=json.loads(safe_get('partial_exit_history', '[]'))
                )
                
                positions[row['stock_code']] = position
            
            self.logger.info(f"✅ 활성 포지션 {len(positions)}개 로드 완료")
            return positions
            
        except Exception as e:
            self.logger.error(f"❌ 활성 포지션 로드 실패: {e}")
            return {}
    
    def get_recent_candidates(self, days: int = 7) -> List[PatternResult]:
        """
        최근 후보종목 조회
        
        Args:
            days: 조회할 일수
            
        Returns:
            List[PatternResult]: 후보종목 리스트
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return []
            
            cursor.execute("""
                SELECT * FROM candidate_stocks 
                WHERE screening_date >= date('now', '-{} days')
                ORDER BY screening_date DESC, confidence DESC
            """.format(days))
            
            candidates = []
            for row in cursor.fetchall():
                # enum 타입 복원
                try:
                    pattern_type = PatternType(row['pattern_type'])
                except ValueError:
                    pattern_type = PatternType.HAMMER  # 기본값
                
                # MarketCapType 안전하게 변환
                try:
                    market_cap_type = MarketCapType(row['market_cap_type'])
                except ValueError:
                    # 기존 값이 다른 형태일 경우 매핑
                    market_cap_str = row['market_cap_type'].lower()
                    if 'large' in market_cap_str or 'big' in market_cap_str:
                        market_cap_type = MarketCapType.LARGE_CAP
                    elif 'small' in market_cap_str:
                        market_cap_type = MarketCapType.SMALL_CAP
                    else:
                        market_cap_type = MarketCapType.MID_CAP  # 기본값
                
                candidate = PatternResult(
                    stock_code=row['stock_code'],
                    stock_name=row['stock_name'],
                    pattern_type=pattern_type,
                    pattern_strength=row['pattern_strength'],
                    current_price=row['current_price'],
                    target_price=row['target_price'],
                    stop_loss=row['stop_loss'],
                    market_cap_type=market_cap_type,
                    volume_ratio=row['volume_ratio'],
                    technical_score=row['technical_score'],
                    pattern_date=row['pattern_date'],
                    confidence=row['confidence']
                )
                candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"❌ 최근 후보종목 조회 실패: {e}")
            return []
    
    def get_trade_history(self, stock_code: Optional[str] = None, days: int = 30) -> List[TradeRecord]:
        """
        거래 기록 조회
        
        Args:
            stock_code: 종목코드 (선택사항)
            days: 조회할 일수
            
        Returns:
            List[TradeRecord]: 거래 기록 리스트
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return []
            
            if stock_code:
                cursor.execute("""
                    SELECT * FROM trade_records 
                    WHERE stock_code = ? AND timestamp >= datetime('now', '-{} days')
                    ORDER BY timestamp DESC
                """.format(days), (stock_code,))
            else:
                cursor.execute("""
                    SELECT * FROM trade_records 
                    WHERE timestamp >= datetime('now', '-{} days')
                    ORDER BY timestamp DESC
                """.format(days))
            
            records = []
            for row in cursor.fetchall():
                record = TradeRecord(
                    timestamp=ensure_kst(datetime.fromisoformat(row['timestamp'])),
                    trade_type=row['trade_type'],
                    stock_code=row['stock_code'],
                    stock_name=row['stock_name'],
                    quantity=row['quantity'],
                    price=row['price'],
                    amount=row['amount'],
                    reason=row['reason'],
                    order_id=row['order_id'],
                    success=bool(row['success']),
                    message=row['message'],
                    commission=row['commission'],
                    tax=row['tax'],
                    net_amount=row['net_amount'],
                    profit_loss=row['profit_loss'],
                    execution_time=ensure_kst(datetime.fromisoformat(row['execution_time'])) if row['execution_time'] else None
                )
                records.append(record)
            
            return records
            
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 조회 실패: {e}")
            return []
    
    def save_account_snapshot(self, snapshot: AccountSnapshot) -> Optional[int]:
        """
        계좌 스냅샷 저장
        
        Args:
            snapshot: 계좌 스냅샷
            
        Returns:
            Optional[int]: 저장된 스냅샷 ID
        """
        try:
            cursor = self._get_cursor()
            if cursor is None:
                return None
            
            cursor.execute("""
                INSERT INTO account_snapshots (
                    timestamp, total_value, available_amount, stock_value,
                    cash_balance, profit_loss, profit_loss_rate, position_count,
                    daily_trades, daily_profit_loss
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.timestamp,
                snapshot.total_value,
                snapshot.available_amount,
                snapshot.stock_value,
                snapshot.cash_balance,
                snapshot.profit_loss,
                snapshot.profit_loss_rate,
                snapshot.position_count,
                snapshot.daily_trades,
                snapshot.daily_profit_loss
            ))
            
            snapshot_id = cursor.lastrowid
            self._commit()
            
            return snapshot_id
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 스냅샷 저장 실패: {e}")
            self._rollback()
            return None
    
    def close(self) -> None:
        """데이터베이스 연결 종료"""
        try:
            if self.connection:
                self.connection.close()
                self.logger.info("✅ 데이터베이스 연결 종료")
        except Exception as e:
            self.logger.error(f"❌ 데이터베이스 연결 종료 실패: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 