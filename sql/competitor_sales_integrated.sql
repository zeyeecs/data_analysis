-- 三店整合销售分析：F / R / V 目录聚合后纵向合并（长表，便于对比）
-- 由 Python 传入各店 snapshot_date；某店日期为 NULL 时该店无行。
-- 不在此 SQL 内做跨店 join；V 的 product_name 映射为 model 与 F/R 对齐。

WITH f_agg AS (
    SELECT
        'F' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand, model, condition
),
r_agg AS (
    SELECT
        'R' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand, model, condition
),
v_agg AS (
    SELECT
        'V' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand, product_name, condition, currency
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, brand, model, condition, currency;
