"""
데이터베이스 매니저 클래스

매매 기록, 포지션, 후보종목 정보를 SQLite 데이터베이스에 저장하고 관리합니다.
프로그램 재시작 시 기존 포지션 복원을 지원합니다.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from utils.logger import setup_logger
from utils.korean_time import now_kst
from core.models import Position, TradingSignal, TradeRecord, AccountSnapshot
from core.enums import PositionStatus, SignalType, OrderType, OrderStatus
from trading.candidate_screener import PatternResult
from trading.pattern_detector import PatternType
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
        cursor = self.connection.cursor()
        
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
        
        self.connection.commit()
    
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
            cursor = self.connection.cursor()
            candidate_ids = []
            
            # 기존 같은 날짜의 후보종목 삭제
            cursor.execute("DELETE FROM candidate_stocks WHERE screening_date = ?", (screening_date,))
            
            # 새 후보종목 저장
            for candidate in candidates:
                cursor.execute("""
                    INSERT INTO candidate_stocks (
                        stock_code, stock_name, pattern_type, pattern_strength,
                        current_price, target_price, stop_loss, market_cap_type,
                        volume_ratio, technical_score, pattern_date, confidence, screening_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    screening_date
                ))
                candidate_ids.append(cursor.lastrowid)
            
            self.connection.commit()
            self.logger.info(f"✅ 후보종목 {len(candidates)}개 저장 완료")
            return candidate_ids
            
        except Exception as e:
            self.logger.error(f"❌ 후보종목 저장 실패: {e}")
            self.connection.rollback()
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
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO positions (
                    stock_code, stock_name, quantity, avg_price, current_price,
                    profit_loss, profit_loss_rate, entry_time, last_update,
                    status, order_type, stop_loss_price, take_profit_price,
                    entry_reason, notes, target_price, original_candidate_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                getattr(position, 'target_price', None),
                candidate_id
            ))
            
            position_id = cursor.lastrowid
            self.connection.commit()
            
            self.logger.info(f"✅ 포지션 저장 완료: {position.stock_name} ({position.stock_code})")
            return position_id
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 저장 실패: {e}")
            self.connection.rollback()
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
            cursor = self.connection.cursor()
            
            cursor.execute("""
                UPDATE positions SET
                    quantity = ?, avg_price = ?, current_price = ?,
                    profit_loss = ?, profit_loss_rate = ?, last_update = ?,
                    status = ?, stop_loss_price = ?, take_profit_price = ?,
                    notes = ?
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
                position.stock_code
            ))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 업데이트 실패: {e}")
            self.connection.rollback()
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
            cursor = self.connection.cursor()
            
            cursor.execute("DELETE FROM positions WHERE stock_code = ?", (stock_code,))
            self.connection.commit()
            
            self.logger.info(f"✅ 포지션 삭제 완료: {stock_code}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 삭제 실패: {e}")
            self.connection.rollback()
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
            cursor = self.connection.cursor()
            
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
            self.connection.commit()
            
            self.logger.info(f"✅ 거래 기록 저장 완료: {trade_record.trade_type} {trade_record.stock_name}")
            return trade_id
            
        except Exception as e:
            self.logger.error(f"❌ 거래 기록 저장 실패: {e}")
            self.connection.rollback()
            return None
    
    def load_active_positions(self) -> Dict[str, Position]:
        """
        활성 포지션 조회 (프로그램 재시작 시 복원용)
        
        Returns:
            Dict[str, Position]: 종목코드를 키로 하는 포지션 딕셔너리
        """
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT * FROM positions 
                WHERE status = 'ACTIVE' AND quantity > 0
                ORDER BY entry_time DESC
            """)
            
            positions = {}
            for row in cursor.fetchall():
                position = Position(
                    stock_code=row['stock_code'],
                    stock_name=row['stock_name'],
                    quantity=row['quantity'],
                    avg_price=row['avg_price'],
                    current_price=row['current_price'],
                    profit_loss=row['profit_loss'],
                    profit_loss_rate=row['profit_loss_rate'],
                    entry_time=datetime.fromisoformat(row['entry_time']),
                    last_update=datetime.fromisoformat(row['last_update']),
                    status=PositionStatus(row['status']),
                    order_type=OrderType(row['order_type']),
                    stop_loss_price=row['stop_loss_price'],
                    take_profit_price=row['take_profit_price'],
                    entry_reason=row['entry_reason'] or '',
                    notes=row['notes'] or ''
                )
                
                # 추가 필드 설정
                if row['target_price']:
                    position.target_price = row['target_price']
                
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
            cursor = self.connection.cursor()
            
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
                
                try:
                    market_cap_type = MarketCapType(row['market_cap_type'])
                except ValueError:
                    market_cap_type = MarketCapType.MIDCAP  # 기본값
                
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
            cursor = self.connection.cursor()
            
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
                    timestamp=datetime.fromisoformat(row['timestamp']),
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
                    execution_time=datetime.fromisoformat(row['execution_time']) if row['execution_time'] else None
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
            cursor = self.connection.cursor()
            
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
            self.connection.commit()
            
            return snapshot_id
            
        except Exception as e:
            self.logger.error(f"❌ 계좌 스냅샷 저장 실패: {e}")
            self.connection.rollback()
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