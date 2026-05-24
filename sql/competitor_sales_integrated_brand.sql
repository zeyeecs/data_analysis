-- 三店整合（单日 · 按品牌汇总）

WITH f_agg AS (
    SELECT
        'F' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand
),
r_agg AS (
    SELECT
        'R' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand
),
v_agg AS (
    SELECT
        'V' AS shop,
        snapshot_date,
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
    WHERE %s::date IS NOT NULL AND snapshot_date = %s::date
    GROUP BY snapshot_date, brand
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, brand;
