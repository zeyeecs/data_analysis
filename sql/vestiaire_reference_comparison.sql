-- 竞品三方参照对照：竞品 V 锚定，竞品 F / R 各做最近邻配对（<=3 天，平手取较早）
-- 用法（psql）:
--   \set anchor_date '2025-03-05'
--   \i sql/vestiaire_reference_comparison.sql

WITH f_dates AS (
    SELECT DISTINCT snapshot_date AS d
    FROM "F"
    WHERE snapshot_date IS NOT NULL
),
r_dates AS (
    SELECT DISTINCT snapshot_date AS d
    FROM "R"
    WHERE snapshot_date IS NOT NULL
),
paired_f AS (
    SELECT pd AS f_date
    FROM (
        SELECT
            d AS pd,
            ABS(d - :'anchor_date'::date) AS delta
        FROM f_dates
    ) sub
    WHERE delta <= 3
    ORDER BY delta ASC, pd ASC
    LIMIT 1
),
paired_r AS (
    SELECT pd AS r_date
    FROM (
        SELECT
            d AS pd,
            ABS(d - :'anchor_date'::date) AS delta
        FROM r_dates
    ) sub
    WHERE delta <= 3
    ORDER BY delta ASC, pd ASC
    LIMIT 1
),
pairing AS (
    SELECT
        :'anchor_date'::date AS v_date,
        (SELECT f_date FROM paired_f) AS f_date,
        (SELECT r_date FROM paired_r) AS r_date
),
v_agg AS (
    SELECT
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
    INNER JOIN pairing p ON "V".snapshot_date = p.v_date
    GROUP BY brand, product_name, condition, currency
),
f_agg AS (
    SELECT
        brand,
        model,
        condition,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        SUM(price) AS total_price
    FROM "F"
    INNER JOIN pairing p ON "F".snapshot_date = p.f_date
    WHERE p.f_date IS NOT NULL
    GROUP BY brand, model, condition
),
r_agg AS (
    SELECT
        brand,
        model,
        condition,
        COUNT(*)::bigint AS item_count,
        AVG(price) AS avg_price,
        MIN(price) AS min_price,
        MAX(price) AS max_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        SUM(price) AS total_price
    FROM "R"
    INNER JOIN pairing p ON "R".snapshot_date = p.r_date
    WHERE p.r_date IS NOT NULL
    GROUP BY brand, model, condition
),
f_combined AS (
    SELECT
        '竞品F' AS shop,
        p.v_date,
        p.f_date AS shop_date,
        ABS(p.f_date - p.v_date) AS pairing_gap_days,
        COALESCE(v.brand, f.brand) AS brand,
        COALESCE(v.model, f.model) AS model,
        COALESCE(v.condition, f.condition) AS condition,
        v.currency,
        v.item_count AS v_item_count,
        v.avg_price AS v_avg_price,
        v.min_price AS v_min_price,
        v.max_price AS v_max_price,
        v.median_price AS v_median_price,
        v.total_price AS v_total_price,
        f.item_count AS shop_item_count,
        f.avg_price AS shop_avg_price,
        f.min_price AS shop_min_price,
        f.max_price AS shop_max_price,
        f.median_price AS shop_median_price,
        f.total_price AS shop_total_price
    FROM pairing p
    CROSS JOIN v_agg v
    FULL OUTER JOIN f_agg f
        ON COALESCE(v.brand, '') = COALESCE(f.brand, '')
        AND COALESCE(v.model, '') = COALESCE(f.model, '')
        AND COALESCE(v.condition, '') = COALESCE(f.condition, '')
    WHERE p.f_date IS NOT NULL
),
r_combined AS (
    SELECT
        '竞品R' AS shop,
        p.v_date,
        p.r_date AS shop_date,
        ABS(p.r_date - p.v_date) AS pairing_gap_days,
        COALESCE(v.brand, r.brand) AS brand,
        COALESCE(v.model, r.model) AS model,
        COALESCE(v.condition, r.condition) AS condition,
        v.currency,
        v.item_count AS v_item_count,
        v.avg_price AS v_avg_price,
        v.min_price AS v_min_price,
        v.max_price AS v_max_price,
        v.median_price AS v_median_price,
        v.total_price AS v_total_price,
        r.item_count AS shop_item_count,
        r.avg_price AS shop_avg_price,
        r.min_price AS shop_min_price,
        r.max_price AS shop_max_price,
        r.median_price AS shop_median_price,
        r.total_price AS shop_total_price
    FROM pairing p
    CROSS JOIN v_agg v
    FULL OUTER JOIN r_agg r
        ON COALESCE(v.brand, '') = COALESCE(r.brand, '')
        AND COALESCE(v.model, '') = COALESCE(r.model, '')
        AND COALESCE(v.condition, '') = COALESCE(r.condition, '')
    WHERE p.r_date IS NOT NULL
)
SELECT * FROM f_combined
UNION ALL
SELECT * FROM r_combined
ORDER BY shop, brand, model, condition, currency;
