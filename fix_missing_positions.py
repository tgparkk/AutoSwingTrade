"""
누락된 positions 데이터 추가 스크립트

2025-07-08에 매수했지만 positions 테이블에 insert되지 않은 
3개 종목의 포지션 데이터를 추가합니다.
"""
import sqlite3
from datetime import datetime


def add_missing_positions():
    """누락된 포지션 데이터 추가"""
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    
    try:
        print("=== 누락된 positions 데이터 추가 시작 ===")
        
        # 추가할 포지션 데이터 (사용자 제공 정보 기준)
        missing_positions = [
            {
                'stock_code': '000810',  # 삼성화재
                'stock_name': '삼성화재',
                'quantity': 3,
                'avg_price': 440500.0,
                'current_price': 440500.0,  # 매수가로 초기화
                'profit_loss': 0.0,
                'profit_loss_rate': 0.0,
                'entry_time': '2025-07-08 09:00:00',
                'entry_reason': '패턴 매수 - 수동 복원'
            },
            {
                'stock_code': '018250',  # 애경산업
                'stock_name': '애경산업', 
                'quantity': 121,
                'avg_price': 16330.0,
                'current_price': 16330.0,  # 매수가로 초기화
                'profit_loss': 0.0,
                'profit_loss_rate': 0.0,
                'entry_time': '2025-07-08 09:00:00',
                'entry_reason': '패턴 매수 - 수동 복원'
            },
            {
                'stock_code': '123700',  # SJM (대교)
                'stock_name': 'SJM',
                'quantity': 577,
                'avg_price': 2380.0,
                'current_price': 2380.0,  # 매수가로 초기화
                'profit_loss': 0.0,
                'profit_loss_rate': 0.0,
                'entry_time': '2025-07-08 09:00:00',
                'entry_reason': '패턴 매수 - 수동 복원'
            }
        ]
        
        # 1. 현재 positions 테이블 상태 확인
        cursor.execute("SELECT stock_code, stock_name, quantity, avg_price FROM positions")
        existing_positions = cursor.fetchall()
        print(f"📊 현재 보유 포지션: {len(existing_positions)}개")
        for pos in existing_positions:
            print(f"  {pos[1]} ({pos[0]}): {pos[2]}주 @ {pos[3]:,}원")
        
        # 2. 누락된 포지션 확인 및 추가
        positions_to_add = []
        
        for pos_data in missing_positions:
            # 이미 존재하는지 확인
            cursor.execute(
                "SELECT COUNT(*) FROM positions WHERE stock_code = ?", 
                (pos_data['stock_code'],)
            )
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                positions_to_add.append(pos_data)
                print(f"✅ 추가 대상: {pos_data['stock_name']} ({pos_data['stock_code']}) "
                      f"{pos_data['quantity']}주 @ {pos_data['avg_price']:,}원")
            else:
                print(f"⚠️ 이미 존재: {pos_data['stock_name']} ({pos_data['stock_code']})")
        
        if positions_to_add:
            print(f"\n📋 추가할 포지션: {len(positions_to_add)}개")
            
            # 사용자 확인
            response = input(f"\n위 {len(positions_to_add)}개의 포지션을 추가하시겠습니까? (y/N): ")
            
            if response.lower() == 'y':
                # 포지션 데이터 추가
                for pos_data in positions_to_add:
                    insert_sql = '''
                        INSERT INTO positions (
                            stock_code, stock_name, quantity, avg_price, current_price,
                            profit_loss, profit_loss_rate, entry_time, last_update,
                            status, order_type, entry_reason, notes, partial_sold
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                    
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute(insert_sql, (
                        pos_data['stock_code'],
                        pos_data['stock_name'], 
                        pos_data['quantity'],
                        pos_data['avg_price'],
                        pos_data['current_price'],
                        pos_data['profit_loss'],
                        pos_data['profit_loss_rate'],
                        pos_data['entry_time'],
                        current_time,  # last_update
                        'ACTIVE',  # status
                        'LIMIT',   # order_type
                        pos_data['entry_reason'],
                        '수동 복원된 포지션',  # notes
                        0  # partial_sold (False)
                    ))
                    
                    print(f"✅ 추가 완료: {pos_data['stock_name']} "
                          f"{pos_data['quantity']}주 @ {pos_data['avg_price']:,}원")
                
                conn.commit()
                print(f"\n✅ {len(positions_to_add)}개의 포지션이 성공적으로 추가되었습니다.")
                
                # 추가 후 상태 확인
                cursor.execute("SELECT COUNT(*) FROM positions")
                total_positions = cursor.fetchone()[0]
                print(f"📊 추가 후 총 포지션: {total_positions}개")
                
            else:
                print("❌ 포지션 추가가 취소되었습니다.")
        else:
            print("✅ 추가할 포지션이 없습니다.")
        
        # 3. SQL Insert 문 출력 (참고용)
        print("\n=== 수동 실행용 SQL Insert 문 ===")
        for pos_data in missing_positions:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"""
INSERT INTO positions (
    stock_code, stock_name, quantity, avg_price, current_price,
    profit_loss, profit_loss_rate, entry_time, last_update,
    status, order_type, entry_reason, notes, partial_sold
) VALUES (
    '{pos_data['stock_code']}', '{pos_data['stock_name']}', 
    {pos_data['quantity']}, {pos_data['avg_price']}, {pos_data['current_price']},
    {pos_data['profit_loss']}, {pos_data['profit_loss_rate']}, 
    '{pos_data['entry_time']}', '{current_time}',
    'ACTIVE', 'LIMIT', '{pos_data['entry_reason']}', '수동 복원된 포지션', 0
);""")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    add_missing_positions() 