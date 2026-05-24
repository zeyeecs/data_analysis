-- 三店整合：在 snapshot_date 闭区间 [start, end] 内聚合
-- Python 参数：start, end（各传 3 次，对应 F/R/V）
-- period 模式：区间内所有快照合并为一行目录维度（跨日累加件数与金额）

WITH f_agg AS (
    SELECT
        'F' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        model,
        condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "F"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand, model, condition
),
r_agg AS (
    SELECT
        'R' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        model,
        condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "R"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand, model, condition
),
v_agg AS (
    SELECT
        'V' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        product_name AS model,
        condition,
        currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "V"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand, product_name, condition, currency
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, brand, model, condition, currency;
