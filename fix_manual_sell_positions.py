#!/usr/bin/env python3
"""
수작업 매도 포지션 정리 스크립트

정전으로 인해 수작업으로 매도한 포지션들을 데이터베이스에서 정리합니다.
'금강공업'을 제외한 모든 포지션에 대해:
1. 매도 거래 기록을 trade_records 테이블에 추가
2. positions 테이블에서 해당 포지션 삭제
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import sys
import os

# 프로젝트 루트 디렉터리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from utils.korean_time import now_kst
except ImportError:
    # 한국 시간 모듈을 불러올 수 없는 경우 대체 함수 사용
    def now_kst():
        """한국 시간 반환 (대체 함수)"""
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst)


def connect_database(db_path: str = "trading_data.db") -> sqlite3.Connection:
    """데이터베이스 연결"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        print(f"✅ 데이터베이스 연결 성공: {db_path}")
        return conn
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        sys.exit(1)


def get_positions_except_target(conn: sqlite3.Connection, exclude_name: str = "금강공업") -> List[Dict[str, Any]]:
    """'금강공업'을 제외한 모든 활성 포지션 조회"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM positions 
            WHERE stock_name != ? AND status = 'ACTIVE' AND quantity > 0
            ORDER BY stock_name
        """, (exclude_name,))
        
        positions = []
        for row in cursor.fetchall():
            position = dict(row)
            positions.append(position)
        
        print(f"📊 '{exclude_name}'을 제외한 활성 포지션 {len(positions)}개 발견")
        for pos in positions:
            print(f"   - {pos['stock_name']} ({pos['stock_code']}): {pos['quantity']}주 @ {pos['avg_price']:,.0f}원")
        
        return positions
        
    except Exception as e:
        print(f"❌ 포지션 조회 실패: {e}")
        return []


def create_sell_trade_records(conn: sqlite3.Connection, positions: List[Dict[str, Any]]) -> bool:
    """매도 거래 기록 생성"""
    try:
        cursor = conn.cursor()
        current_time = now_kst()
        
        print(f"\n📝 매도 거래 기록 생성 중...")
        
        for position in positions:
            # 매도 거래 기록 생성
            cursor.execute("""
                INSERT INTO trade_records (
                    timestamp, trade_type, stock_code, stock_name, quantity,
                    price, amount, reason, order_id, success, message,
                    commission, tax, net_amount, profit_loss, execution_time, position_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                current_time.strftime('%Y-%m-%d %H:%M:%S'),  # timestamp
                'SELL',                                        # trade_type
                position['stock_code'],                        # stock_code
                position['stock_name'],                        # stock_name
                position['quantity'],                          # quantity
                position['current_price'],                     # price (현재가로 매도했다고 가정)
                position['quantity'] * position['current_price'],  # amount
                '정전으로 인한 수작업 매도',                    # reason
                f"MANUAL_{current_time.strftime('%Y%m%d_%H%M%S')}_{position['stock_code']}",  # order_id
                True,                                          # success
                '수작업 매도 완료',                            # message
                0.0,                                           # commission
                0.0,                                           # tax
                position['quantity'] * position['current_price'],  # net_amount
                position['profit_loss'],                       # profit_loss
                current_time.strftime('%Y-%m-%d %H:%M:%S'),   # execution_time
                position['id']                                 # position_id
            ))
            
            print(f"   ✅ {position['stock_name']}: {position['quantity']}주 @ {position['current_price']:,.0f}원 매도 기록 생성")
        
        conn.commit()
        print(f"✅ 총 {len(positions)}개 매도 거래 기록 생성 완료")
        return True
        
    except Exception as e:
        print(f"❌ 매도 거래 기록 생성 실패: {e}")
        conn.rollback()
        return False


def remove_sold_positions(conn: sqlite3.Connection, positions: List[Dict[str, Any]]) -> bool:
    """매도된 포지션 삭제"""
    try:
        cursor = conn.cursor()
        
        print(f"\n🗑️ 매도된 포지션 삭제 중...")
        
        for position in positions:
            cursor.execute("DELETE FROM positions WHERE id = ?", (position['id'],))
            print(f"   ✅ {position['stock_name']} 포지션 삭제 완료")
        
        conn.commit()
        print(f"✅ 총 {len(positions)}개 포지션 삭제 완료")
        return True
        
    except Exception as e:
        print(f"❌ 포지션 삭제 실패: {e}")
        conn.rollback()
        return False


def verify_remaining_positions(conn: sqlite3.Connection) -> None:
    """남은 포지션 확인"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT stock_name, stock_code, quantity, avg_price, current_price, profit_loss
            FROM positions 
            WHERE status = 'ACTIVE' AND quantity > 0
            ORDER BY stock_name
        """)
        
        remaining = cursor.fetchall()
        
        print(f"\n📊 남은 활성 포지션: {len(remaining)}개")
        if remaining:
            for row in remaining:
                print(f"   - {row['stock_name']} ({row['stock_code']}): {row['quantity']}주 @ {row['avg_price']:,.0f}원 (손익: {row['profit_loss']:+,.0f}원)")
        else:
            print("   없음")
        
    except Exception as e:
        print(f"❌ 남은 포지션 조회 실패: {e}")


def main():
    """메인 실행 함수"""
    print("🔧 수작업 매도 포지션 정리 스크립트 시작")
    print("=" * 60)
    
    # 데이터베이스 연결
    conn = connect_database()
    
    try:
        # 1. '금강공업'을 제외한 포지션 조회
        positions_to_sell = get_positions_except_target(conn, "금강공업")
        
        if not positions_to_sell:
            print("📊 정리할 포지션이 없습니다.")
            return
        
        # 확인 요청
        print(f"\n⚠️ 위 {len(positions_to_sell)}개 종목에 대해 매도 기록을 생성하고 포지션을 삭제합니다.")
        response = input("계속하시겠습니까? (y/N): ").strip().lower()
        
        if response != 'y':
            print("❌ 작업이 취소되었습니다.")
            return
        
        # 2. 매도 거래 기록 생성
        if not create_sell_trade_records(conn, positions_to_sell):
            print("❌ 매도 거래 기록 생성에 실패했습니다.")
            return
        
        # 3. 포지션 삭제
        if not remove_sold_positions(conn, positions_to_sell):
            print("❌ 포지션 삭제에 실패했습니다.")
            return
        
        # 4. 결과 확인
        verify_remaining_positions(conn)
        
        print("\n" + "=" * 60)
        print("✅ 수작업 매도 포지션 정리 완료!")
        
    except Exception as e:
        print(f"❌ 작업 중 오류 발생: {e}")
        
    finally:
        conn.close()
        print("📝 데이터베이스 연결 종료")


if __name__ == "__main__":
    main() 