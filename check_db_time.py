"""
데이터베이스 시간 확인 스크립트

candidate_stocks 테이블의 created_at 컬럼이 한국시간과 맞는지 확인합니다.
"""

import sqlite3
from datetime import datetime
from utils.korean_time import now_kst

def check_database_time():
    """데이터베이스의 시간 데이터 확인"""
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect('trading_data.db')
        cursor = conn.cursor()
        
        print("🕐 현재 한국시간:", now_kst().strftime('%Y-%m-%d %H:%M:%S'))
        print("🕐 현재 시스템시간:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print()
        
        # candidate_stocks 테이블의 최근 데이터 확인
        print("📊 candidate_stocks 테이블의 최근 데이터:")
        cursor.execute("""
            SELECT stock_name, created_at, screening_date 
            FROM candidate_stocks 
            ORDER BY rowid DESC 
            LIMIT 5
        """)
        
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  - {row[0]}: created_at={row[1]}, screening_date={row[2]}")
        else:
            print("  데이터가 없습니다.")
        
        print()
        
        # positions 테이블의 시간 데이터도 확인
        print("📊 positions 테이블의 시간 데이터:")
        cursor.execute("""
            SELECT stock_name, entry_time, last_update 
            FROM positions 
            ORDER BY rowid DESC 
            LIMIT 5
        """)
        
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  - {row[0]}: entry_time={row[1]}, last_update={row[2]}")
        else:
            print("  데이터가 없습니다.")
        
        print()
        
        # trade_records 테이블의 시간 데이터도 확인
        print("📊 trade_records 테이블의 시간 데이터:")
        cursor.execute("""
            SELECT stock_name, timestamp, execution_time 
            FROM trade_records 
            ORDER BY rowid DESC 
            LIMIT 3
        """)
        
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  - {row[0]}: timestamp={row[1]}, execution_time={row[2]}")
        else:
            print("  데이터가 없습니다.")
        
        print()
        
        # 테이블 스키마 확인
        print("📊 candidate_stocks 테이블 스키마:")
        cursor.execute("PRAGMA table_info(candidate_stocks)")
        schema = cursor.fetchall()
        for col in schema:
            if 'created_at' in col[1] or 'time' in col[1] or 'date' in col[1]:
                print(f"  - {col[1]}: {col[2]} (기본값: {col[4]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_database_time() 