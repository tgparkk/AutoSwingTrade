-- TCC스틸(002710) 매도 거래 기록 INSERT 쿼리
-- positions 테이블 데이터 기반 (ID: 45)

INSERT INTO trade_records (
    timestamp,
    trade_type,
    stock_code,
    stock_name,
    quantity,
    price,
    amount,
    reason,
    order_id,
    success,
    message,
    commission,
    tax,
    net_amount,
    profit_loss,
    execution_time,
    position_id
) VALUES (
    '2025-07-21 19:33:55',                      -- timestamp: 매도 시점 (positions last_update 시간)
    'SELL',                                     -- trade_type: 매도
    '002710',                                   -- stock_code: TCC스틸
    'TCC스틸',                                  -- stock_name
    114,                                        -- quantity: 114주
    18300.0,                                    -- price: 18,300원 (현재가)
    2086200.0,                                  -- amount: 114주 × 18,300원 = 2,086,200원
    '오류로 인한 수동 매도 기록 복원',           -- reason
    'MANUAL_20250721_193355_002710',           -- order_id: 수동 생성 ID
    1,                                          -- success: TRUE (1)
    '매도 거래 기록 수동 복원 완료',             -- message
    0.0,                                        -- commission: 수수료 (0으로 설정)
    0.0,                                        -- tax: 세금 (0으로 설정)
    2086200.0,                                  -- net_amount: 순 거래금액
    0.0,                                        -- profit_loss: 손익 (매수가와 매도가 동일하므로 0)
    '2025-07-21 19:33:55',                     -- execution_time: 체결 시간
    45                                          -- position_id: positions 테이블의 해당 레코드 ID
);

-- 확인용 쿼리
SELECT 
    tr.timestamp,
    tr.trade_type,
    tr.stock_code,
    tr.stock_name,
    tr.quantity,
    tr.price,
    tr.amount,
    tr.profit_loss,
    tr.reason,
    tr.order_id
FROM trade_records tr
WHERE tr.stock_code = '002710' 
  AND tr.trade_type = 'SELL'
  AND tr.timestamp >= '2025-07-21 00:00:00'
ORDER BY tr.timestamp DESC
LIMIT 1; 