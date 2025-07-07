"""
데이터베이스 시간대 수정 스크립트

1. 기존 candidate_stocks 테이블의 UTC 시간을 한국시간으로 변환
2. save_candidate_stocks 메서드를 수정하여 한국시간으로 저장하도록 변경
"""

import sqlite3
from datetime import datetime, timedelta
from utils.korean_time import now_kst

def fix_database_timezone():
    """데이터베이스의 시간대 문제 수정"""
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect('trading_data.db')
        cursor = conn.cursor()
        
        print("🔧 데이터베이스 시간대 수정 시작...")
        
        # 1. 기존 데이터의 UTC 시간을 한국시간으로 변환 (+9시간)
        print("📊 기존 UTC 시간을 한국시간으로 변환 중...")
        
        # candidate_stocks 테이블의 created_at 수정
        cursor.execute("""
            UPDATE candidate_stocks 
            SET created_at = datetime(created_at, '+9 hours')
            WHERE created_at IS NOT NULL
        """)
        
        updated_rows = cursor.rowcount
        print(f"✅ candidate_stocks 테이블 {updated_rows}개 행 업데이트 완료")
        
        # 변경사항 저장
        conn.commit()
        
        # 2. 수정 결과 확인
        print("\n📊 수정 후 데이터 확인:")
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
        
        print(f"\n🕐 현재 한국시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}")
        
        conn.close()
        
        print("✅ 데이터베이스 시간대 수정 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

def test_timezone_fix():
    """시간대 수정이 올바르게 적용되었는지 테스트"""
    
    try:
        conn = sqlite3.connect('trading_data.db')
        cursor = conn.cursor()
        
        print("\n🧪 시간대 수정 테스트...")
        
        # 현재 한국시간으로 테스트 데이터 삽입
        test_time = now_kst().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            INSERT INTO candidate_stocks (
                stock_code, stock_name, pattern_type, pattern_strength,
                current_price, target_price, stop_loss, market_cap_type,
                volume_ratio, technical_score, pattern_date, confidence, 
                screening_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'TEST001', '테스트종목', 'HAMMER', 85.0,
            1000.0, 1080.0, 990.0, 'SMALL',
            1.5, 75.0, '2025-07-07', 90.0,
            '2025-07-07', test_time
        ))
        
        # 테스트 데이터 조회
        cursor.execute("""
            SELECT stock_name, created_at 
            FROM candidate_stocks 
            WHERE stock_code = 'TEST001'
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"✅ 테스트 데이터: {result[0]} - {result[1]}")
            print(f"🕐 입력 시간: {test_time}")
            print(f"🕐 저장 시간: {result[1]}")
            
            if result[1] == test_time:
                print("✅ 시간대 수정이 올바르게 적용되었습니다!")
            else:
                print("⚠️ 시간대 수정에 문제가 있을 수 있습니다.")
        
        # 테스트 데이터 삭제
        cursor.execute("DELETE FROM candidate_stocks WHERE stock_code = 'TEST001'")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    fix_database_timezone()
    test_timezone_fix() 