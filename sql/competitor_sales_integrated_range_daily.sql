-- 三店整合：区间内按 snapshot_date 逐日保留（便于看趋势）
-- Python 参数：start, end（各传 3 次）

WITH f_agg AS (
    SELECT
        'F' AS shop,
        snapshot_date,
        snapshot_date AS period_start,
        snapshot_date AS period_end,
        1::bigint AS snapshot_days,
        brand,
        model,
        condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        SUM(price) AS total_price
    FROM "F"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY snapshot_date, brand, model, condition
),
r_agg AS (
    SELECT
        'R' AS shop,
        snapshot_date,
        snapshot_date AS period_start,
        snapshot_date AS period_end,
        1::bigint AS snapshot_days,
        brand,
        model,
        condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        SUM(price) AS total_price
    FROM "R"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY snapshot_date, brand, model, condition
),
v_agg AS (
    SELECT
        'V' AS shop,
        snapshot_date,
        snapshot_date AS period_start,
        snapshot_date AS period_end,
        1::bigint AS snapshot_days,
        brand,
        product_name AS model,
        condition,
        currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        SUM(price) AS total_price
    FROM "V"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY snapshot_date, brand, product_name, condition, currency
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, snapshot_date, brand, model, condition, currency;
