-- 业务数据表 F / R / V（三家竞品店铺 · 均为已售快照）
-- F: 竞品店 F 已售
-- R: 竞品店 R 已售（列结构与 F 相同）
-- V: 竞品店 V 已售（导出列更全，含 currency / sold_at 等）

DROP TABLE IF EXISTS "F" CASCADE;
DROP TABLE IF EXISTS "R" CASCADE;
DROP TABLE IF EXISTS "V" CASCADE;

CREATE TABLE "F" (
    id              BIGSERIAL PRIMARY KEY,
    item_id         TEXT,
    brand           TEXT,
    model           TEXT,
    condition       TEXT,
    price           NUMERIC,
    color           TEXT,
    image_path      TEXT,
    image_urls      TEXT,
    snapshot_date   DATE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE "R" (
    id              BIGSERIAL PRIMARY KEY,
    item_id         TEXT,
    brand           TEXT,
    model           TEXT,
    condition       TEXT,
    price           NUMERIC,
    color           TEXT,
    image_path      TEXT,
    image_urls      TEXT,
    snapshot_date   DATE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_f_snapshot ON "F" (snapshot_date);
CREATE INDEX idx_f_snapshot_agg ON "F" (snapshot_date)
    INCLUDE (brand, model, condition, price);
CREATE INDEX idx_f_item_id ON "F" (item_id);
CREATE INDEX idx_r_snapshot ON "R" (snapshot_date);
CREATE INDEX idx_r_snapshot_agg ON "R" (snapshot_date)
    INCLUDE (brand, model, condition, price);
CREATE INDEX idx_r_item_id ON "R" (item_id);

CREATE TABLE "V" (
    id              BIGSERIAL PRIMARY KEY,
    image           TEXT,
    item_id         TEXT,
    brand           TEXT,
    product_name    TEXT,
    material        TEXT,
    color           TEXT,
    size            TEXT,
    price           NUMERIC,
    currency        TEXT,
    seller_price    NUMERIC,
    buyer_fee       NUMERIC,
    likes           INTEGER,
    listed_at       TIMESTAMPTZ,
    sold_at         TIMESTAMPTZ,
    condition       TEXT,
    url             TEXT,
    snapshot_date   DATE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_v_snapshot ON "V" (snapshot_date);
CREATE INDEX idx_v_snapshot_agg ON "V" (snapshot_date)
    INCLUDE (brand, product_name, condition, currency, price);
CREATE INDEX idx_v_item_id ON "V" (item_id);
