import { neon } from "@neondatabase/serverless";

export function getSql() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("缺少 DATABASE_URL 环境变量");
  }
  return neon(url);
}

export type TableBounds = Record<string, { min: string | null; max: string | null }>;

export type TrendRow = {
  snapshot_date: string;
  currency: string;
  item_count: number;
  total_price: number;
  min_price: number;
  max_price: number;
  median_price: number;
  avg_price: number;
};

/** 与 sql/model_price_trend_daily.sql + src/analysis.fetch_model_price_trend 一致 */
export async function fetchTableBounds(): Promise<TableBounds> {
  const sql = getSql();
  const rows = await sql`
    SELECT 'F' AS tbl, MIN(snapshot_date) AS min_d, MAX(snapshot_date) AS max_d
    FROM "F" WHERE snapshot_date IS NOT NULL
    UNION ALL
    SELECT 'R', MIN(snapshot_date), MAX(snapshot_date)
    FROM "R" WHERE snapshot_date IS NOT NULL
    UNION ALL
    SELECT 'V', MIN(snapshot_date), MAX(snapshot_date)
    FROM "V" WHERE snapshot_date IS NOT NULL
  `;

  const out: TableBounds = {};
  for (const row of rows) {
    const minD = row.min_d;
    const maxD = row.max_d;
    out[String(row.tbl)] = {
      min: minD ? String(minD).slice(0, 10) : null,
      max: maxD ? String(maxD).slice(0, 10) : null,
    };
  }
  return out;
}

export async function fetchModelPriceTrend(
  start: string,
  end: string,
  modelKeyword: string,
): Promise<TrendRow[]> {
  const pat = `%${modelKeyword.trim()}%`;
  const sql = getSql();

  const rows = await sql`
    WITH raw AS (
      SELECT snapshot_date, price, NULL::text AS currency
      FROM "F"
      WHERE snapshot_date BETWEEN ${start}::date AND ${end}::date
        AND model ILIKE ${pat}

      UNION ALL

      SELECT snapshot_date, price, NULL::text AS currency
      FROM "R"
      WHERE snapshot_date BETWEEN ${start}::date AND ${end}::date
        AND model ILIKE ${pat}

      UNION ALL

      SELECT snapshot_date, price, currency
      FROM "V"
      WHERE snapshot_date BETWEEN ${start}::date AND ${end}::date
        AND product_name ILIKE ${pat}
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
    ORDER BY snapshot_date, currency
  `;

  return rows.map((row) => {
    const itemCount = Number(row.item_count);
    const totalPrice = Number(row.total_price);
    return {
      snapshot_date: String(row.snapshot_date).slice(0, 10),
      currency: String(row.currency),
      item_count: itemCount,
      total_price: totalPrice,
      min_price: Number(row.min_price),
      max_price: Number(row.max_price),
      median_price: Number(row.median_price),
      avg_price: itemCount > 0 ? totalPrice / itemCount : 0,
    };
  });
}
