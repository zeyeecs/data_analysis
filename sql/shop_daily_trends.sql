-- 三店按 snapshot_date 的日度汇总（轻量，适合趋势图）
-- Python 参数：start, end（各传 3 次）

SELECT
    'F' AS shop,
    snapshot_date,
    COUNT(*)::bigint AS item_count,
    SUM(price) AS total_price
FROM "F"
WHERE snapshot_date BETWEEN %s::date AND %s::date
GROUP BY snapshot_date

UNION ALL

SELECT
    'R' AS shop,
    snapshot_date,
    COUNT(*)::bigint AS item_count,
    SUM(price) AS total_price
FROM "R"
WHERE snapshot_date BETWEEN %s::date AND %s::date
GROUP BY snapshot_date

UNION ALL

SELECT
    'V' AS shop,
    snapshot_date,
    COUNT(*)::bigint AS item_count,
    SUM(price) AS total_price
FROM "V"
WHERE snapshot_date BETWEEN %s::date AND %s::date
GROUP BY snapshot_date

ORDER BY snapshot_date, shop
