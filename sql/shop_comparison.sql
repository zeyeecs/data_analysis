-- 竞品两两对照：竞品 F 锚定 snapshot_date，竞品 R 最近邻配对（<=3 天，平手取较早）
-- 用法（psql）:
--   \set anchor_date '2025-03-01'
--   \i sql/shop_comparison.sql

WITH r_dates AS (
    SELECT DISTINCT snapshot_date AS d
    FROM "R"
    WHERE snapshot_date IS NOT NULL
),
paired AS (
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
        :'anchor_date'::date AS f_date,
        r_date
    FROM paired
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
    GROUP BY brand, model, condition
),
combined AS (
    SELECT
        COALESCE(f.brand, r.brand) AS brand,
        COALESCE(f.model, r.model) AS model,
        COALESCE(f.condition, r.condition) AS condition,
        f.item_count AS f_item_count,
        f.avg_price AS f_avg_price,
        f.min_price AS f_min_price,
        f.max_price AS f_max_price,
        f.median_price AS f_median_price,
        f.total_price AS f_total_price,
        r.item_count AS r_item_count,
        r.avg_price AS r_avg_price,
        r.min_price AS r_min_price,
        r.max_price AS r_max_price,
        r.median_price AS r_median_price,
        r.total_price AS r_total_price
    FROM f_agg f
    FULL OUTER JOIN r_agg r
        ON COALESCE(f.brand, '') = COALESCE(r.brand, '')
        AND COALESCE(f.model, '') = COALESCE(r.model, '')
        AND COALESCE(f.condition, '') = COALESCE(r.condition, '')
)
SELECT
    p.f_date,
    p.r_date,
    ABS(p.r_date - p.f_date) AS pairing_gap_days,
    c.brand,
    c.model,
    c.condition,
    c.f_item_count,
    c.f_avg_price,
    c.f_min_price,
    c.f_max_price,
    c.f_median_price,
    c.f_total_price,
    c.r_item_count,
    c.r_avg_price,
    c.r_min_price,
    c.r_max_price,
    c.r_median_price,
    c.r_total_price
FROM pairing p
CROSS JOIN combined c
ORDER BY c.brand, c.model, c.condition;
