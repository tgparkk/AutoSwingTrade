-- LG에너지솔루션(373220) positions 테이블 복원 쿼리
-- 2025-07-11 08:36:47 매수 체결분 (로그 기반)

INSERT INTO positions (
    stock_code,
    stock_name,
    quantity,
    avg_price,
    current_price,
    profit_loss,
    profit_loss_rate,
    entry_time,
    last_update,
    status,
    order_type,
    stop_loss_price,
    take_profit_price,
    entry_reason,
    notes,
    target_price,
    partial_sold,
    pattern_type,
    market_cap_type,
    pattern_strength,
    volume_ratio
) VALUES (
    '373220',                                    -- stock_code: LG에너지솔루션
    'LG에너지솔루션',                             -- stock_name
    7,                                           -- quantity: 7주 (로그에서 확인)
    318000.0,                                    -- avg_price: 318,000원 (로그에서 확인)
    318000.0,                                    -- current_price: 진입가와 동일
    0.0,                                         -- profit_loss: 진입 시점이므로 0
    0.0,                                         -- profit_loss_rate: 진입 시점이므로 0
    '2025-07-11 08:36:47',                      -- entry_time: 로그 시간
    '2025-07-11 08:36:47',                      -- last_update: 로그 시간
    'ACTIVE',                                    -- status
    'LIMIT',                                     -- order_type
    307824.0,                                    -- stop_loss_price: 307,824원 (로그에서 확인)
    349800.0,                                    -- take_profit_price: 349,800원 (로그에서 확인)
    '패턴: morning_star, 신뢰도: 100.0%',        -- entry_reason
    '자동매매 체결',                              -- notes
    349800.0,                                    -- target_price: 349,800원 (로그에서 확인)
    0,                                           -- partial_sold: FALSE
    'morning_star',                              -- pattern_type: 샛별 패턴 (로그에서 확인)
    'large_cap',                                 -- market_cap_type: 대형주 (로그에서 확인)
    3.0,                                         -- pattern_strength: 3.0 (로그에서 확인)
    1.9                                          -- volume_ratio: 1.9배 (로그에서 확인)
);

-- 실행 후 확인 쿼리
SELECT * FROM positions WHERE stock_code = '373220'; 