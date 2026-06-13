import "@/lib/load-database-env";

import type {
  BreakdownItem,
  FilterOptions,
  MatchedProduct,
  ProductAnalysis,
  ProductSample,
  ProductSamplesResult,
  ProductTrendPoint,
} from "@/data/schema";
import {
  colorsExcludeFilterSql,
  colorsFilterSql,
  conditionsExcludeFilterSql,
  conditionsFilterSql,
  expandSlashTokenOptions,
  materialsExcludeFilterSql,
  materialsFilterSql,
  yearsExcludeFilterSql,
  yearsFilterSql,
} from "@/lib/attribute-filters";
import { formatCondition, sortConditionBreakdown } from "@/lib/condition";
import { firstHttpImageUrl } from "@/lib/sample-image";
import { isTransientDbError } from "@/lib/database-url";
import { toIsoDateString } from "@/lib/dates";
import { prisma } from "@/lib/prisma";
import { Prisma } from "@prisma/client";

const SHOP_CODES = ["F", "R", "V"] as const;
export type ShopCode = (typeof SHOP_CODES)[number];

export type ProductAnalysisParams = {
  keywords: string[];
  colors?: string[];
  excludeColors?: string[];
  conditions?: string[];
  excludeConditions?: string[];
  materials?: string[];
  excludeMaterials?: string[];
  years?: string[];
  excludeYears?: string[];
  shops?: string[];
  startDate?: string;
  endDate?: string;
  brand?: string;
  productName?: string;
};

function resolveShopCodes(shops?: string[]): ShopCode[] {
  const normalized =
    shops
      ?.map((shop) => shop.trim().toUpperCase())
      .filter((shop): shop is ShopCode => SHOP_CODES.includes(shop as ShopCode)) ?? [];
  return normalized.length > 0 ? normalized : [...SHOP_CODES];
}

export type ProductSamplesParams = ProductAnalysisParams & {
  page?: number;
  pageSize?: number;
};

const DEFAULT_SAMPLE_PAGE_SIZE = 20;
const MAX_SAMPLE_PAGE_SIZE = 100;

async function withDbRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
      const message = err instanceof Error ? err.message : String(err);
      if (!isTransientDbError(message) || i === attempts - 1) throw err;
      await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
    }
  }
  throw last;
}

function parseKeywords(raw: string | null | undefined): string[] {
  if (!raw?.trim()) return [];
  return raw
    .split(/[\s,，]+/)
    .map((k) => k.trim())
    .filter(Boolean);
}

export function parseProductAnalysisParams(searchParams: URLSearchParams): ProductAnalysisParams {
  const colors = searchParams
    .getAll("color")
    .map((v) => v.trim())
    .filter(Boolean);
  const conditions = searchParams
    .getAll("condition")
    .map((v) => v.trim())
    .filter(Boolean);
  const materials = searchParams
    .getAll("material")
    .map((v) => v.trim())
    .filter(Boolean);
  const years = searchParams
    .getAll("year")
    .map((v) => v.trim())
    .filter(Boolean);
  const shops = searchParams
    .getAll("shop")
    .map((v) => v.trim())
    .filter(Boolean);
  const excludeColors = searchParams
    .getAll("excludeColor")
    .map((v) => v.trim())
    .filter(Boolean);
  const excludeConditions = searchParams
    .getAll("excludeCondition")
    .map((v) => v.trim())
    .filter(Boolean);
  const excludeMaterials = searchParams
    .getAll("excludeMaterial")
    .map((v) => v.trim())
    .filter(Boolean);
  const excludeYears = searchParams
    .getAll("excludeYear")
    .map((v) => v.trim())
    .filter(Boolean);
  return {
    keywords: parseKeywords(searchParams.get("q")),
    colors: colors.length > 0 ? colors : undefined,
    excludeColors: excludeColors.length > 0 ? excludeColors : undefined,
    conditions: conditions.length > 0 ? conditions : undefined,
    excludeConditions: excludeConditions.length > 0 ? excludeConditions : undefined,
    materials: materials.length > 0 ? materials : undefined,
    excludeMaterials: excludeMaterials.length > 0 ? excludeMaterials : undefined,
    years: years.length > 0 ? years : undefined,
    excludeYears: excludeYears.length > 0 ? excludeYears : undefined,
    shops: shops.length > 0 ? shops : undefined,
    startDate: searchParams.get("start")?.trim() || undefined,
    endDate: searchParams.get("end")?.trim() || undefined,
    brand: searchParams.get("brand")?.trim() || undefined,
    productName: searchParams.get("product")?.trim() || undefined,
  };
}

export function parseProductSamplesParams(searchParams: URLSearchParams): ProductSamplesParams {
  const pageRaw = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const pageSizeRaw = Number.parseInt(
    searchParams.get("pageSize") ?? String(DEFAULT_SAMPLE_PAGE_SIZE),
    10,
  );

  return {
    ...parseProductAnalysisParams(searchParams),
    page: Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1,
    pageSize:
      Number.isFinite(pageSizeRaw) && pageSizeRaw > 0
        ? Math.min(pageSizeRaw, MAX_SAMPLE_PAGE_SIZE)
        : DEFAULT_SAMPLE_PAGE_SIZE,
  };
}

function keywordMatchSql(textExpr: string, keywords: string[]): Prisma.Sql {
  if (keywords.length === 0) return Prisma.empty;
  const parts = keywords.map(
    (kw) => Prisma.sql`${Prisma.raw(textExpr)} ILIKE ${`%${kw}%`}`,
  );
  return Prisma.join(parts, " AND ");
}

function dateRangeFilter(startDate?: string, endDate?: string): Prisma.Sql {
  const parts: Prisma.Sql[] = [];
  if (startDate) parts.push(Prisma.sql`snapshot_date >= ${startDate}::date`);
  if (endDate) parts.push(Prisma.sql`snapshot_date <= ${endDate}::date`);
  if (parts.length === 0) return Prisma.empty;
  return Prisma.join(parts, " AND ");
}

/** 仅统计已录入价格的商品（排除 NULL 与 0）。 */
function recordedPriceFilter(): Prisma.Sql {
  return Prisma.sql`price IS NOT NULL AND price > 0`;
}

function optionalFilter(column: string, value: string | undefined): Prisma.Sql {
  if (!value) return Prisma.empty;
  return Prisma.sql`${Prisma.raw(column)} = ${value}`;
}

function productNameFilter(column: "model" | "product_name", name?: string): Prisma.Sql {
  if (!name) return Prisma.empty;
  return Prisma.sql`${Prisma.raw(column)} = ${name}`;
}

function buildWhereClause(
  params: ProductAnalysisParams,
  opts: { textExpr: string; productColumn: "model" | "product_name" },
): Prisma.Sql {
  const kw = keywordMatchSql(opts.textExpr, params.keywords);
  const dates = dateRangeFilter(params.startDate, params.endDate);

  const parts = Prisma.join(
    [
      dates !== Prisma.empty ? dates : null,
      kw !== Prisma.empty ? kw : null,
      colorsFilterSql(params.colors),
      colorsExcludeFilterSql(params.excludeColors),
      conditionsFilterSql(params.conditions),
      conditionsExcludeFilterSql(params.excludeConditions),
      materialsFilterSql(params.materials),
      materialsExcludeFilterSql(params.excludeMaterials),
      yearsFilterSql(params.years),
      yearsExcludeFilterSql(params.excludeYears),
      optionalFilter("brand", params.brand),
      productNameFilter(opts.productColumn, params.productName),
      recordedPriceFilter(),
    ].filter((p): p is Prisma.Sql => p !== null && p !== Prisma.empty),
    " AND ",
  );

  return parts === Prisma.empty ? recordedPriceFilter() : parts;
}

function buildAttrsUnion(params: ProductAnalysisParams, frText: string, vText: string): Prisma.Sql {
  const shops = resolveShopCodes(params.shops);
  const frClause = buildWhereClause(params, { textExpr: frText, productColumn: "model" });
  const vClause = buildWhereClause(params, { textExpr: vText, productColumn: "product_name" });
  const parts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    parts.push(Prisma.sql`
      SELECT
        COALESCE(NULLIF(TRIM(condition), ''), '未知') AS condition,
        COALESCE(NULLIF(TRIM(color), ''), '未知') AS color
      FROM "F"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("R")) {
    parts.push(Prisma.sql`
      SELECT
        COALESCE(NULLIF(TRIM(condition), ''), '未知') AS condition,
        COALESCE(NULLIF(TRIM(color), ''), '未知') AS color
      FROM "R"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("V")) {
    parts.push(Prisma.sql`
      SELECT
        COALESCE(NULLIF(TRIM(condition), ''), '未知') AS condition,
        COALESCE(NULLIF(TRIM(color), ''), '未知') AS color
      FROM "V"
      WHERE ${vClause}
    `);
  }

  return Prisma.join(parts, " UNION ALL ");
}

function productLabelSql(brandCol: string, nameCol: string): Prisma.Sql {
  return Prisma.sql`NULLIF(TRIM(COALESCE(${Prisma.raw(brandCol)}, '') || ' ' || COALESCE(${Prisma.raw(nameCol)}, '')), '')`;
}

function buildRawUnion(params: ProductAnalysisParams, frText: string, vText: string): Prisma.Sql {
  const shops = resolveShopCodes(params.shops);
  const frClause = buildWhereClause(params, { textExpr: frText, productColumn: "model" });
  const vClause = buildWhereClause(params, { textExpr: vText, productColumn: "product_name" });
  const parts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price
      FROM "F"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("R")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price
      FROM "R"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("V")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price
      FROM "V"
      WHERE ${vClause}
    `);
  }

  return Prisma.join(parts, " UNION ALL ");
}

/** 含商品名，用于按日定位最低价/最高价对应 SKU */
function buildRawDetailedUnion(
  params: ProductAnalysisParams,
  frText: string,
  vText: string,
): Prisma.Sql {
  const shops = resolveShopCodes(params.shops);
  const frClause = buildWhereClause(params, { textExpr: frText, productColumn: "model" });
  const vClause = buildWhereClause(params, { textExpr: vText, productColumn: "product_name" });
  const frLabel = productLabelSql("brand", "model");
  const vLabel = productLabelSql("brand", "product_name");
  const parts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price, ${frLabel} AS product_label
      FROM "F"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("R")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price, ${frLabel} AS product_label
      FROM "R"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("V")) {
    parts.push(Prisma.sql`
      SELECT snapshot_date, price::float8 AS price, ${vLabel} AS product_label
      FROM "V"
      WHERE ${vClause}
    `);
  }

  return Prisma.join(parts, " UNION ALL ");
}

function buildSampleRowsUnion(
  params: ProductAnalysisParams,
  frText: string,
  vText: string,
): Prisma.Sql {
  const shops = resolveShopCodes(params.shops);
  const frClause = buildWhereClause(params, { textExpr: frText, productColumn: "model" });
  const vClause = buildWhereClause(params, { textExpr: vText, productColumn: "product_name" });
  const parts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    parts.push(Prisma.sql`
      SELECT
        'F'::text AS shop,
        id,
        item_id,
        brand,
        model AS product_name,
        TRIM(condition) AS item_condition,
        color,
        price::float8 AS price,
        snapshot_date,
        image_path,
        image_urls,
        NULL::text AS image
      FROM "F"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("R")) {
    parts.push(Prisma.sql`
      SELECT
        'R'::text AS shop,
        id,
        item_id,
        brand,
        model AS product_name,
        TRIM(condition) AS item_condition,
        color,
        price::float8 AS price,
        snapshot_date,
        image_path,
        image_urls,
        NULL::text AS image
      FROM "R"
      WHERE ${frClause}
    `);
  }
  if (shops.includes("V")) {
    parts.push(Prisma.sql`
      SELECT
        'V'::text AS shop,
        id,
        item_id,
        brand,
        product_name,
        TRIM(condition) AS item_condition,
        color,
        price::float8 AS price,
        snapshot_date,
        NULL::text AS image_path,
        NULL::text AS image_urls,
        image
      FROM "V"
      WHERE ${vClause}
    `);
  }

  return Prisma.join(parts, " UNION ALL ");
}

function buildMatchedProductsUnion(
  params: ProductAnalysisParams,
  frText: string,
  vText: string,
): Prisma.Sql {
  const shops = resolveShopCodes(params.shops);
  const frClause = buildWhereClause(params, { textExpr: frText, productColumn: "model" });
  const vClause = buildWhereClause(params, { textExpr: vText, productColumn: "product_name" });
  const parts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    parts.push(Prisma.sql`
      SELECT brand, model AS product_name, 'F'::text AS shop
      FROM "F"
      WHERE ${frClause}
        AND brand IS NOT NULL AND brand <> ''
        AND model IS NOT NULL AND model <> ''
    `);
  }
  if (shops.includes("R")) {
    parts.push(Prisma.sql`
      SELECT brand, model AS product_name, 'R'::text AS shop
      FROM "R"
      WHERE ${frClause}
        AND brand IS NOT NULL AND brand <> ''
        AND model IS NOT NULL AND model <> ''
    `);
  }
  if (shops.includes("V")) {
    parts.push(Prisma.sql`
      SELECT brand, product_name, 'V'::text AS shop
      FROM "V"
      WHERE ${vClause}
        AND brand IS NOT NULL AND brand <> ''
        AND product_name IS NOT NULL AND product_name <> ''
    `);
  }

  return Prisma.join(parts, " UNION ALL ");
}

type SummaryRow = {
  sample_count: bigint | number;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
};

type TrendRow = {
  snapshot_date: Date | string;
  item_count: bigint | number;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
  min_price_products: string | null;
  max_price_products: string | null;
};

type OptionRow = { value: string };

type ProductRow = {
  brand: string;
  product_name: string;
  sample_count: bigint | number;
  shops: string[];
  matched_product_count: bigint | number;
};

type BreakdownRow = {
  label: string;
  cnt: bigint | number;
};

type SampleRow = {
  shop: string;
  id: bigint | number;
  item_id: string | null;
  brand: string | null;
  product_name: string | null;
  item_condition: string | null;
  color: string | null;
  price: number;
  snapshot_date: Date | string | null;
  image_path: string | null;
  image_urls: string | null;
  image: string | null;
};

function toBreakdownItems(rows: BreakdownRow[], total: number): BreakdownItem[] {
  if (total <= 0) return [];
  return rows.map((row) => {
    const count = Number(row.cnt);
    const percentage = Math.round((count / total) * 1000) / 10;
    return { label: row.label, count, percentage };
  });
}

function toQueryScopeParams(params: ProductAnalysisParams): ProductAnalysisParams {
  return {
    ...params,
    brand: undefined,
    productName: undefined,
  };
}

/** 成色分布：不含成色筛选项，避免多选时图表只剩已勾选项；保留选中单品。 */
function toConditionBreakdownParams(params: ProductAnalysisParams): ProductAnalysisParams {
  return {
    ...params,
    conditions: undefined,
  };
}

/** 颜色分布：不含颜色筛选项；保留选中单品。 */
function toColorBreakdownParams(params: ProductAnalysisParams): ProductAnalysisParams {
  return {
    ...params,
    colors: undefined,
  };
}

const CONDITION_BREAKDOWN_LIMIT = 12;
const COLOR_BREAKDOWN_LIMIT = 8;

async function fetchQueryScopeSampleCount(attrs: Prisma.Sql): Promise<number> {
  const rows = await prisma.$queryRaw<{ cnt: bigint | number }[]>`
    WITH attrs AS (${attrs})
    SELECT COUNT(*)::bigint AS cnt FROM attrs
  `;
  return Number(rows[0]?.cnt ?? 0);
}

async function fetchAttributeBreakdowns(
  conditionAttrs: Prisma.Sql,
  colorAttrs: Prisma.Sql,
  conditionTotal: number,
  colorTotal: number,
): Promise<{ breakdownByCondition: BreakdownItem[]; breakdownByColor: BreakdownItem[] }> {
  const [conditionRows, colorRows] = await Promise.all([
    prisma.$queryRaw<BreakdownRow[]>`
      WITH attrs AS (${conditionAttrs})
      SELECT condition AS label, COUNT(*)::bigint AS cnt
      FROM attrs
      GROUP BY condition
      ORDER BY cnt DESC, label
      LIMIT ${CONDITION_BREAKDOWN_LIMIT}
    `,
    prisma.$queryRaw<BreakdownRow[]>`
      WITH attrs AS (${colorAttrs})
      SELECT color AS label, COUNT(*)::bigint AS cnt
      FROM attrs
      GROUP BY color
      ORDER BY cnt DESC, label
      LIMIT ${COLOR_BREAKDOWN_LIMIT}
    `,
  ]);

  return {
    breakdownByCondition: sortConditionBreakdown(
      toBreakdownItems(conditionRows, conditionTotal),
    ),
    breakdownByColor: toBreakdownItems(colorRows, colorTotal),
  };
}

export async function fetchProductAnalysis(params: ProductAnalysisParams): Promise<ProductAnalysis> {
  return withDbRetry(async () => fetchProductAnalysisOnce(params));
}

async function fetchProductAnalysisOnce(params: ProductAnalysisParams): Promise<ProductAnalysis> {
  const frText = `(COALESCE(brand, '') || ' ' || COALESCE(model, ''))`;
  const vText = `(COALESCE(brand, '') || ' ' || COALESCE(product_name, ''))`;
  const raw = buildRawUnion(params, frText, vText);
  const rawDetailed = buildRawDetailedUnion(params, frText, vText);

  // 匹配商品列表与 Top 5：搜索范围（不含选中单品）；成色/颜色分布含选中单品
  const queryScopeParams = toQueryScopeParams(params);
  const conditionBreakdownParams = toConditionBreakdownParams(params);
  const colorBreakdownParams = toColorBreakdownParams(params);
  const conditionAttrs = buildAttrsUnion(conditionBreakdownParams, frText, vText);
  const colorAttrs = buildAttrsUnion(colorBreakdownParams, frText, vText);
  const matched = buildMatchedProductsUnion(queryScopeParams, frText, vText);

  const [summaryRows, trendRows, productRows] = await Promise.all([
    prisma.$queryRaw<SummaryRow[]>`
      WITH raw AS (${raw})
      SELECT
        COUNT(*)::bigint AS sample_count,
        AVG(price)::float8 AS avg_price,
        MIN(price)::float8 AS min_price,
        MAX(price)::float8 AS max_price
      FROM raw
    `,
    prisma.$queryRaw<TrendRow[]>`
      WITH raw AS (${rawDetailed}),
      daily AS (
        SELECT
          snapshot_date,
          COUNT(*)::bigint AS item_count,
          AVG(price)::float8 AS avg_price,
          MIN(price)::float8 AS min_price,
          MAX(price)::float8 AS max_price
        FROM raw
        WHERE snapshot_date IS NOT NULL
        GROUP BY snapshot_date
      )
      SELECT
        d.snapshot_date,
        d.item_count,
        d.avg_price,
        d.min_price,
        d.max_price,
        (
          SELECT string_agg(DISTINCT r.product_label, '、' ORDER BY r.product_label)
          FROM raw r
          WHERE r.snapshot_date = d.snapshot_date
            AND r.price = d.min_price
            AND r.product_label IS NOT NULL
        ) AS min_price_products,
        (
          SELECT string_agg(DISTINCT r.product_label, '、' ORDER BY r.product_label)
          FROM raw r
          WHERE r.snapshot_date = d.snapshot_date
            AND r.price = d.max_price
            AND r.product_label IS NOT NULL
        ) AS max_price_products
      FROM daily d
      ORDER BY d.snapshot_date ASC
    `,
    prisma.$queryRaw<ProductRow[]>`
      WITH matched AS (${matched}),
      grouped AS (
        SELECT
          brand,
          product_name,
          COUNT(*)::bigint AS sample_count,
          array_agg(DISTINCT shop ORDER BY shop) AS shops
        FROM matched
        GROUP BY brand, product_name
      )
      SELECT
        brand,
        product_name,
        sample_count,
        shops,
        COUNT(*) OVER()::bigint AS matched_product_count
      FROM grouped
      ORDER BY sample_count DESC, brand, product_name
      LIMIT 200
    `,
  ]);

  const summary = summaryRows[0];
  const sampleCount = Number(summary?.sample_count ?? 0);

  const [queryScopeSampleCount, conditionBreakdownTotal, colorBreakdownTotal] =
    await Promise.all([
      fetchQueryScopeSampleCount(buildAttrsUnion(queryScopeParams, frText, vText)),
      fetchQueryScopeSampleCount(conditionAttrs),
      fetchQueryScopeSampleCount(colorAttrs),
    ]);
  const { breakdownByCondition, breakdownByColor } = await fetchAttributeBreakdowns(
    conditionAttrs,
    colorAttrs,
    conditionBreakdownTotal,
    colorBreakdownTotal,
  );

  const trend: ProductTrendPoint[] = trendRows
    .map((row) => {
      const iso = toIsoDateString(row.snapshot_date);
      if (!iso) return null;
      return {
        date: `${iso}T00:00:00`,
        itemCount: Number(row.item_count),
        avgPrice: row.avg_price ?? null,
        minPrice: row.min_price ?? null,
        maxPrice: row.max_price ?? null,
        minPriceProducts: row.min_price_products?.trim() || null,
        maxPriceProducts: row.max_price_products?.trim() || null,
      };
    })
    .filter((row): row is ProductTrendPoint => row !== null);

  const matchedProductCount = Number(productRows[0]?.matched_product_count ?? 0);

  const products: MatchedProduct[] = productRows.map((row) => {
    const brand = row.brand.trim();
    const productName = row.product_name.trim();
    const label = [brand, productName].filter(Boolean).join(" ");
    return {
      brand,
      productName,
      label,
      sampleCount: Number(row.sample_count),
      shops: row.shops ?? [],
    };
  });

  return {
    keywords: params.keywords,
    filters: {
      colors: params.colors ?? null,
      excludeColors: params.excludeColors ?? null,
      conditions: params.conditions ?? null,
      excludeConditions: params.excludeConditions ?? null,
      materials: params.materials ?? null,
      excludeMaterials: params.excludeMaterials ?? null,
      years: params.years ?? null,
      excludeYears: params.excludeYears ?? null,
      shops: params.shops ?? null,
      startDate: params.startDate ?? null,
      endDate: params.endDate ?? null,
      brand: params.brand ?? null,
      productName: params.productName ?? null,
    },
    products,
    matchedProductCount,
    summary: {
      sampleCount,
      avgPrice: summary?.avg_price ?? null,
      minPrice: summary?.min_price ?? null,
      maxPrice: summary?.max_price ?? null,
    },
    trend,
    queryScopeSampleCount,
    breakdownByCondition,
    breakdownByColor,
    conditionBreakdownTotal,
    colorBreakdownTotal,
  };
}

function toProductSample(row: SampleRow): ProductSample | null {
  const snapshotDate = toIsoDateString(row.snapshot_date);
  if (!snapshotDate || row.price == null || row.price <= 0) return null;

  const brand = row.brand?.trim() || null;
  const productName = row.product_name?.trim() || null;
  const label = [brand, productName].filter(Boolean).join(" ") || "—";

  return {
    shop: row.shop,
    itemId: row.item_id?.trim() || null,
    brand,
    productName,
    label,
    condition: formatCondition(row.item_condition),
    color: row.color?.trim() || null,
    price: row.price,
    snapshotDate,
    imageUrl: firstHttpImageUrl(row.image, row.image_urls, row.image_path),
  };
}

export async function fetchProductSamples(
  params: ProductSamplesParams,
): Promise<ProductSamplesResult> {
  return withDbRetry(async () => fetchProductSamplesOnce(params));
}

async function fetchProductSamplesOnce(params: ProductSamplesParams): Promise<ProductSamplesResult> {
  const pageSize = params.pageSize ?? DEFAULT_SAMPLE_PAGE_SIZE;
  const page = params.page ?? 1;
  const offset = (page - 1) * pageSize;

  const frText = `(COALESCE(brand, '') || ' ' || COALESCE(model, ''))`;
  const vText = `(COALESCE(brand, '') || ' ' || COALESCE(product_name, ''))`;
  const samples = buildSampleRowsUnion(params, frText, vText);

  const [countRows, itemRows] = await Promise.all([
    prisma.$queryRaw<{ cnt: bigint | number }[]>`
      WITH samples AS (${samples})
      SELECT COUNT(*)::bigint AS cnt FROM samples
    `,
    prisma.$queryRaw<SampleRow[]>`
      WITH samples AS (${samples})
      SELECT
        shop,
        id,
        item_id,
        brand,
        product_name,
        item_condition,
        color,
        price,
        snapshot_date,
        image_path,
        image_urls,
        image
      FROM samples
      ORDER BY snapshot_date DESC NULLS LAST, shop ASC, id DESC
      LIMIT ${pageSize} OFFSET ${offset}
    `,
  ]);

  const total = Number(countRows[0]?.cnt ?? 0);
  const items = itemRows
    .map((row) => toProductSample(row))
    .filter((row): row is ProductSample => row !== null);

  return { items, total, page, pageSize };
}

export async function fetchFilterOptions(
  params: Pick<ProductAnalysisParams, "keywords" | "shops">,
): Promise<FilterOptions> {
  return withDbRetry(async () => fetchFilterOptionsOnce(params));
}

async function fetchFilterOptionsOnce(
  params: Pick<ProductAnalysisParams, "keywords" | "shops">,
): Promise<FilterOptions> {
  const shops = resolveShopCodes(params.shops);
  const frText = `(COALESCE(brand, '') || ' ' || COALESCE(model, ''))`;
  const vText = `(COALESCE(brand, '') || ' ' || COALESCE(product_name, ''))`;
  const kwFr = keywordMatchSql(frText, params.keywords);
  const kwV = keywordMatchSql(vText, params.keywords);

  const frKw = kwFr !== Prisma.empty ? Prisma.sql`AND ${kwFr}` : Prisma.empty;
  const vKw = kwV !== Prisma.empty ? Prisma.sql`AND ${kwV}` : Prisma.empty;

  const colorParts: Prisma.Sql[] = [];
  const conditionParts: Prisma.Sql[] = [];
  const materialParts: Prisma.Sql[] = [];
  const yearParts: Prisma.Sql[] = [];

  if (shops.includes("F")) {
    colorParts.push(Prisma.sql`SELECT color FROM "F" WHERE color IS NOT NULL AND color <> '' ${frKw}`);
    conditionParts.push(
      Prisma.sql`SELECT condition FROM "F" WHERE condition IS NOT NULL AND condition <> '' ${frKw}`,
    );
    materialParts.push(
      Prisma.sql`SELECT material FROM "F" WHERE material IS NOT NULL AND material <> '' ${frKw}`,
    );
    yearParts.push(Prisma.sql`SELECT year FROM "F" WHERE year IS NOT NULL AND year <> '' ${frKw}`);
  }
  if (shops.includes("R")) {
    colorParts.push(Prisma.sql`SELECT color FROM "R" WHERE color IS NOT NULL AND color <> '' ${frKw}`);
    conditionParts.push(
      Prisma.sql`SELECT condition FROM "R" WHERE condition IS NOT NULL AND condition <> '' ${frKw}`,
    );
    materialParts.push(
      Prisma.sql`SELECT material FROM "R" WHERE material IS NOT NULL AND material <> '' ${frKw}`,
    );
    yearParts.push(Prisma.sql`SELECT year FROM "R" WHERE year IS NOT NULL AND year <> '' ${frKw}`);
  }
  if (shops.includes("V")) {
    colorParts.push(Prisma.sql`SELECT color FROM "V" WHERE color IS NOT NULL AND color <> '' ${vKw}`);
    conditionParts.push(
      Prisma.sql`SELECT condition FROM "V" WHERE condition IS NOT NULL AND condition <> '' ${vKw}`,
    );
    materialParts.push(
      Prisma.sql`SELECT material FROM "V" WHERE material IS NOT NULL AND material <> '' ${vKw}`,
    );
    yearParts.push(Prisma.sql`SELECT year FROM "V" WHERE year IS NOT NULL AND year <> '' ${vKw}`);
  }

  const colors = await prisma.$queryRaw<OptionRow[]>`
    SELECT DISTINCT color AS value FROM (
      ${Prisma.join(colorParts, " UNION ")}
    ) t
    ORDER BY value
  `;

  const conditionRows = await prisma.$queryRaw<OptionRow[]>`
    SELECT DISTINCT condition AS value FROM (
      ${Prisma.join(conditionParts, " UNION ")}
    ) t
    ORDER BY value
  `;

  const materialRows = await prisma.$queryRaw<OptionRow[]>`
    SELECT DISTINCT material AS value FROM (
      ${Prisma.join(materialParts, " UNION ")}
    ) t
    ORDER BY value
  `;

  const yearRows = await prisma.$queryRaw<OptionRow[]>`
    SELECT DISTINCT year AS value FROM (
      ${Prisma.join(yearParts, " UNION ")}
    ) t
    ORDER BY value
  `;

  return {
    colors: expandSlashTokenOptions(colors.map((r) => r.value)),
    conditions: expandSlashTokenOptions(conditionRows.map((r) => r.value)),
    materials: expandSlashTokenOptions(materialRows.map((r) => r.value)),
    years: expandSlashTokenOptions(yearRows.map((r) => r.value)),
  };
}
