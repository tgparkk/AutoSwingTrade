-- 프로그램 오류로 누락된 3개 종목 positions 테이블 수동 삽입
-- 2025-01-08 매수 체결분

-- 1. 대교 (123700) - 샛별 패턴
INSERT INTO positions (
    stock_code, stock_name, quantity, avg_price, current_price,
    profit_loss, profit_loss_rate, entry_time, last_update,
    status, order_type, stop_loss_price, take_profit_price,
    entry_reason, notes, partial_sold, original_candidate_id,
    pattern_type, market_cap_type, pattern_strength, volume_ratio
) VALUES (
    '123700', 'SJM', 577, 2380, 2380,
    0.0, 0.0, '2025-01-08 09:00:00', '2025-01-08 09:00:00',
    'ACTIVE', 'LIMIT', 2237, 2570,
    '패턴: morning_star, 신뢰도: 100.0%', '샛별 패턴 수동 삽입', 0, NULL,
    'morning_star', 'large_cap', 3.0, 1.67
);

-- 2. 애경산업 (018250) - 상승장악형 패턴  
INSERT INTO positions (
    stock_code, stock_name, quantity, avg_price, current_price,
    profit_loss, profit_loss_rate, entry_time, last_update,
    status, order_type, stop_loss_price, take_profit_price,
    entry_reason, notes, partial_sold, original_candidate_id,
    pattern_type, market_cap_type, pattern_strength, volume_ratio
) VALUES (
    '018250', '애경산업', 121, 16330, 16330,
    0.0, 0.0, '2025-01-08 09:00:00', '2025-01-08 09:00:00',
    'ACTIVE', 'LIMIT', 15677, 17147,
    '패턴: bullish_engulfing, 신뢰도: 100.0%', '상승장악형 패턴 수동 삽입', 0, NULL,
    'bullish_engulfing', 'large_cap', 1.25, 1.53
);

-- 3. 삼성화재 (000810) - 망치형 패턴
INSERT INTO positions (
    stock_code, stock_name, quantity, avg_price, current_price,
    profit_loss, profit_loss_rate, entry_time, last_update,
    status, order_type, stop_loss_price, take_profit_price,
    entry_reason, notes, partial_sold, original_candidate_id,
    pattern_type, market_cap_type, pattern_strength, volume_ratio
) VALUES (
    '000810', '삼성화재', 3, 440500, 440500,
    0.0, 0.0, '2025-01-08 09:00:00', '2025-01-08 09:00:00',
    'ACTIVE', 'LIMIT', 427285, 453715,
    '패턴: hammer, 신뢰도: 91.6%', '망치형 패턴 수동 삽입', 0, NULL,
    'hammer', 'large_cap', 1.11, 1.40
);

-- 확인 쿼리
SELECT 
    stock_code, stock_name, quantity, avg_price,
    take_profit_price, stop_loss_price,
    pattern_type, market_cap_type, pattern_strength
FROM positions 
WHERE stock_code IN ('123700', '018250', '000810')
ORDER BY stock_code; 

-- 프로그램 오류로 인해 누락된 positions 테이블 INSERT 문
-- 2025-07-09 매매 체결 데이터 수동 복구

-- 1. 대덕 (008060) - 08:20:01 매수 체결
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
    '008060',                                    -- stock_code
    '대덕',                                      -- stock_name
    301,                                         -- quantity (로그에서 확인)
    8220.0,                                      -- avg_price (로그에서 확인)
    8220.0,                                      -- current_price (진입가와 동일)
    0.0,                                         -- profit_loss (진입 시점이므로 0)
    0.0,                                         -- profit_loss_rate (진입 시점이므로 0)
    '2025-07-09 08:20:01',                      -- entry_time (로그 시간)
    '2025-07-09 08:20:01',                      -- last_update (로그 시간)
    'ACTIVE',                                    -- status
    'LIMIT',                                     -- order_type
    7957.0,                                      -- stop_loss_price (candidate_stocks에서)
    9042.0,                                      -- take_profit_price (candidate_stocks에서)
    '패턴: morning_star, 신뢰도: 100.0%',        -- entry_reason
    '자동매매 체결',                              -- notes
    9042.0,                                      -- target_price (candidate_stocks에서)
    0,                                           -- partial_sold (FALSE)
    'morning_star',                              -- pattern_type (candidate_stocks에서)
    'large_cap',                                 -- market_cap_type (candidate_stocks에서)
    1.54647267223885,                            -- pattern_strength (candidate_stocks에서)
    3.0                                          -- volume_ratio (candidate_stocks에서)
);

-- 2. KR모터스 (000040) - 09:03:46 매수 체결  
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
    '000040',                                    -- stock_code
    'KR모터스',                                  -- stock_name
    5840,                                        -- quantity (로그에서 확인)
    425.0,                                       -- avg_price (로그에서 확인)
    425.0,                                       -- current_price (진입가와 동일)
    0.0,                                         -- profit_loss (진입 시점이므로 0)
    0.0,                                         -- profit_loss_rate (진입 시점이므로 0)
    '2025-07-09 09:03:46',                      -- entry_time (로그 시간)
    '2025-07-09 09:03:46',                      -- last_update (로그 시간)
    'ACTIVE',                                    -- status
    'LIMIT',                                     -- order_type
    411.0,                                       -- stop_loss_price (candidate_stocks에서)
    468.0,                                       -- take_profit_price (candidate_stocks에서)
    '패턴: morning_star, 신뢰도: 100.0%',        -- entry_reason
    '자동매매 체결',                              -- notes
    468.0,                                       -- target_price (candidate_stocks에서)
    0,                                           -- partial_sold (FALSE)
    'morning_star',                              -- pattern_type (candidate_stocks에서)
    'large_cap',                                 -- market_cap_type (candidate_stocks에서)
    2.63523978589186,                            -- pattern_strength (candidate_stocks에서)
    4.0                                          -- volume_ratio (candidate_stocks에서)
);

-- 실행 확인 쿼리
SELECT 
    stock_code,
    stock_name,
    quantity,
    avg_price,
    entry_time,
    pattern_type,
    stop_loss_price,
    take_profit_price
FROM positions 
WHERE stock_code IN ('008060', '000040')
ORDER BY entry_time; 