"""
중복된 trade_records 정리 스크립트

2025-07-08 오전에 발생한 중복 체결 완료 처리로 인한 
중복 trade_records를 정리합니다.
"""
import sqlite3
from datetime import datetime


def clean_duplicate_trades():
    """중복된 매매 기록 정리"""
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    
    try:
        print("=== 중복 trade_records 정리 시작 ===")
        
        # 1. 현재 상태 확인
        cursor.execute('''
            SELECT COUNT(*) FROM trade_records 
            WHERE timestamp >= '2025-07-08 09:00:00'
        ''')
        total_count = cursor.fetchone()[0]
        print(f"📊 2025-07-08 09:00 이후 총 매매 기록: {total_count}건")
        
        # 2. 중복 기록 식별 및 정리
        # 같은 stock_code, trade_type, quantity, price, timestamp(분 단위)를 가진 중복 기록 중
        # 가장 오래된 하나만 남기고 나머지 삭제
        
        cursor.execute('''
            WITH DuplicateGroups AS (
                SELECT 
                    rowid,
                    stock_code,
                    stock_name,
                    trade_type,
                    quantity,
                    price,
                    timestamp,
                    ROW_NUMBER() OVER (
                        PARTITION BY 
                            stock_code, 
                            trade_type, 
                            quantity, 
                            price,
                            strftime('%Y-%m-%d %H:%M', timestamp)
                        ORDER BY rowid ASC
                    ) as row_num
                FROM trade_records
                WHERE timestamp >= '2025-07-08 09:00:00'
            )
            SELECT 
                rowid, stock_name, trade_type, quantity, price, timestamp
            FROM DuplicateGroups 
            WHERE row_num > 1
            ORDER BY stock_code, timestamp
        ''')
        
        duplicates_to_delete = cursor.fetchall()
        
        if duplicates_to_delete:
            print(f"\n📋 삭제할 중복 기록: {len(duplicates_to_delete)}건")
            for record in duplicates_to_delete:
                print(f"  ID:{record[0]} - {record[1]} {record[2]} {record[3]}주 @ {record[4]:,}원 ({record[5]})")
            
            # 사용자 확인
            response = input(f"\n위 {len(duplicates_to_delete)}건의 중복 기록을 삭제하시겠습니까? (y/N): ")
            
            if response.lower() == 'y':
                # 중복 기록 삭제
                delete_ids = [str(record[0]) for record in duplicates_to_delete]
                placeholders = ','.join(['?'] * len(delete_ids))
                
                cursor.execute(f'DELETE FROM trade_records WHERE rowid IN ({placeholders})', delete_ids)
                deleted_count = cursor.rowcount
                
                conn.commit()
                print(f"✅ {deleted_count}건의 중복 기록이 삭제되었습니다.")
                
                # 정리 후 상태 확인
                cursor.execute('''
                    SELECT COUNT(*) FROM trade_records 
                    WHERE timestamp >= '2025-07-08 09:00:00'
                ''')
                remaining_count = cursor.fetchone()[0]
                print(f"📊 정리 후 매매 기록: {remaining_count}건")
                
            else:
                print("❌ 중복 기록 삭제가 취소되었습니다.")
        else:
            print("✅ 중복 기록이 없습니다.")
            
        # 3. 대교우B와 우진아이엔에스 기록 확인
        print("\n=== 문제 종목 기록 확인 ===")
        cursor.execute('''
            SELECT stock_name, trade_type, quantity, price, COUNT(*) as count
            FROM trade_records 
            WHERE (stock_name LIKE '%대교%' OR stock_name LIKE '%우진%')
              AND timestamp >= '2025-07-08 09:00:00'
            GROUP BY stock_name, trade_type, quantity, price
            ORDER BY stock_name, timestamp
        ''')
        
        problem_records = cursor.fetchall()
        for record in problem_records:
            print(f"  {record[0]} {record[1]} {record[2]}주 @ {record[3]:,}원 - {record[4]}건")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    clean_duplicate_trades() 