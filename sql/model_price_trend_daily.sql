-- 匹配型号：全渠道按 snapshot_date 汇总价格（不区分 F/R/V）
-- Python 参数：start, end, model_pat（各传 3 次）

WITH raw AS (
    SELECT snapshot_date, price, NULL::text AS currency
    FROM "F"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
      AND model ILIKE %s

    UNION ALL

    SELECT snapshot_date, price, NULL::text AS currency
    FROM "R"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
      AND model ILIKE %s

    UNION ALL

    SELECT snapshot_date, price, currency
    FROM "V"
    WHERE snapshot_date BETWEEN %s::date AND %s::date
      AND product_name ILIKE %s
)
SELECT
    snapshot_date,
    COALESCE(currency, '—') AS currency,
    COUNT(*)::bigint AS item_count,
    SUM(price) AS total_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price) AS median_price
FROM raw
GROUP BY snapshot_date, currency
ORDER BY snapshot_date, currency;
