-- 加速 snapshot_date 区间聚合（Dashboard / 整合 SQL）
-- 在已有库上执行：python scripts/apply_perf_indexes.py

CREATE INDEX IF NOT EXISTS idx_f_snapshot_agg ON "F" (snapshot_date)
    INCLUDE (brand, model, condition, price);

CREATE INDEX IF NOT EXISTS idx_r_snapshot_agg ON "R" (snapshot_date)
    INCLUDE (brand, model, condition, price);

CREATE INDEX IF NOT EXISTS idx_v_snapshot_agg ON "V" (snapshot_date)
    INCLUDE (brand, product_name, condition, currency, price);
