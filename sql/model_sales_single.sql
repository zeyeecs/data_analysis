-- 三店整合：单日快照 + 型号关键字（F/R model，V product_name）
-- Python 参数：f_date, model_pat, r_date, model_pat, v_date, model_pat

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
    WHERE %s::date IS NOT NULL
      AND snapshot_date = %s::date
      AND model ILIKE %s
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
    WHERE %s::date IS NOT NULL
      AND snapshot_date = %s::date
      AND model ILIKE %s
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
    WHERE %s::date IS NOT NULL
      AND snapshot_date = %s::date
      AND product_name ILIKE %s
    GROUP BY snapshot_date, brand, product_name, condition, currency
)
SELECT * FROM f_agg
UNION ALL
SELECT * FROM r_agg
UNION ALL
SELECT * FROM v_agg
ORDER BY shop, brand, model, condition, currency;
