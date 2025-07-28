-- 포지션 목표가/손절가 업데이트 쿼리
-- 새로운 계산 로직: 거래량, RSI, 기술점수 반영

-- 1. 금강공업 (014280) - 상승장액형 패턴
-- 기본 6% + 거래량 조정(2.25배 → +1%) + RSI 조정(50 → 0%) + 기술점수 조정(3 → 0%) = 7%
-- 대형주 민감도 0.7배 적용 → 최종 약 6.7%
-- 목표가: 4865 * 1.067 = 5193원
-- 손절가: 4865 * (1 - 0.067/2.0) = 4702원 (손익비 2:1)
UPDATE positions 
SET take_profit_price = 5193,
    stop_loss_price = 4702,
    last_update = datetime('now', 'localtime')
WHERE id = 10;

-- 2. LG이노텍 (011070) - 샛별 패턴  
-- 기본 8% + 거래량 조정(3.72배 → +1%) + RSI 조정(50 → 0%) + 기술점수 조정(3 → 0%) = 9%
-- 대형주 민감도 0.7배 적용 → 최종 약 8.6%
-- 목표가: 157900 * 1.086 = 171481원
-- 손절가: 157900 * (1 - 0.086/2.5) = 156358원 (손익비 2.5:1)
UPDATE positions 
SET take_profit_price = 171481,
    stop_loss_price = 156358,
    last_update = datetime('now', 'localtime')
WHERE id = 17;

-- 3. 한미약품 (128940) - 샛별 패턴
-- 기본 8% + 거래량 조정(1.68배 → 0%) + RSI 조정(50 → 0%) + 기술점수 조정(3 → 0%) = 8%
-- 대형주 민감도 0.7배 적용 → 최종 약 7.6%
-- 목표가: 286000 * 1.076 = 307736원
-- 손절가: 286000 * (1 - 0.076/2.5) = 277282원 (손익비 2.5:1)
UPDATE positions 
SET take_profit_price = 307736,
    stop_loss_price = 277282,
    last_update = datetime('now', 'localtime')
WHERE id = 18;

-- 4. 한올바이오파마 (009420) - 샛별 패턴
-- 기본 8% + 거래량 조정(2.69배 → +1%) + RSI 조정(50 → 0%) + 기술점수 조정(3 → 0%) = 9%
-- 대형주 민감도 0.7배 적용 → 최종 약 8.6%
-- 목표가: 27000 * 1.086 = 29324원
-- 손절가: 27000 * (1 - 0.086/2.5) = 26072원 (손익비 2.5:1)
UPDATE positions 
SET take_profit_price = 29324,
    stop_loss_price = 26072,
    last_update = datetime('now', 'localtime')
WHERE id = 19;

-- 전체 업데이트를 한 번에 실행하는 경우
/*
UPDATE positions 
SET take_profit_price = CASE 
    WHEN id = 10 THEN 5193
    WHEN id = 17 THEN 171481
    WHEN id = 18 THEN 307736
    WHEN id = 19 THEN 29324
    ELSE take_profit_price
END,
stop_loss_price = CASE 
    WHEN id = 10 THEN 4702
    WHEN id = 17 THEN 156358
    WHEN id = 18 THEN 277282
    WHEN id = 19 THEN 26072
    ELSE stop_loss_price
END,
last_update = datetime('now', 'localtime')
WHERE id IN (10, 17, 18, 19);
*/

-- 변경사항 확인 쿼리
SELECT 
    id,
    stock_code,
    stock_name,
    current_price,
    take_profit_price,
    stop_loss_price,
    ROUND((take_profit_price - current_price) * 100.0 / current_price, 2) as target_return_pct,
    ROUND((current_price - stop_loss_price) * 100.0 / current_price, 2) as stop_loss_pct,
    ROUND((take_profit_price - current_price) / (current_price - stop_loss_price), 2) as risk_reward_ratio,
    pattern_type,
    volume_ratio
FROM positions 
WHERE id IN (10, 17, 18, 19)
ORDER BY id; 