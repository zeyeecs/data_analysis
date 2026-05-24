-- 三店整合（按品牌汇总）：行数远少于目录级，适合 Dashboard 首屏
-- Python 参数：start, end（各传 3 次）

WITH f_agg AS (
    SELECT
        'F' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        NULL::text AS model,
        NULL::text AS condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "F"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand
),
r_agg AS (
    SELECT
        'R' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        NULL::text AS model,
        NULL::text AS condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "R"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand
),
v_agg AS (
    SELECT
        'V' AS shop,
        MIN(snapshot_date) AS period_start,
        MAX(snapshot_date) AS period_end,
        COUNT(DISTINCT snapshot_date)::bigint AS snapshot_days,
        brand,
        NULL::text AS model,
        NULL::text AS condition,
        NULL::text AS currency,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        NULL::numeric AS median_price,
        SUM(price) AS total_price
    FROM "V"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
    GROUP BY brand
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, brand;
