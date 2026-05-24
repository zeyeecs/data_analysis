import type { TableBounds } from "./db";

/** 与 src/analysis.default_period_bounds 一致 */
export function defaultPeriodBounds(
  bounds: TableBounds,
  days = 30,
): { start: string; end: string } {
  const mins: string[] = [];
  const maxs: string[] = [];

  for (const { min, max } of Object.values(bounds)) {
    if (min) mins.push(min);
    if (max) maxs.push(max);
  }

  const today = new Date();
  const isoToday = today.toISOString().slice(0, 10);

  if (maxs.length === 0) {
    const start = new Date(today);
    start.setDate(start.getDate() - days);
    return { start: start.toISOString().slice(0, 10), end: isoToday };
  }

  const end = maxs.sort().at(-1)!;
  const dataStart = mins.length > 0 ? mins.sort()[0]! : end;
  const endDate = new Date(end + "T00:00:00");
  const windowStart = new Date(endDate);
  windowStart.setDate(windowStart.getDate() - days);
  const windowIso = windowStart.toISOString().slice(0, 10);
  const start = windowIso > dataStart ? windowIso : dataStart;

  return { start, end };
}

export function periodFromPreset(bounds: TableBounds, days: number) {
  return defaultPeriodBounds(bounds, days);
}

export function normalizeRange(start: string, end: string) {
  return start <= end ? { start, end } : { start: end, end: start };
}

export type PeriodSummary = {
  itemCount: number;
  avgPrice: number | null;
  minPrice: number;
  maxPrice: number;
  snapshotDays: number;
};

export function buildPeriodSummary(
  rows: {
    item_count: number;
    total_price: number;
    min_price: number;
    max_price: number;
    snapshot_date: string;
  }[],
): PeriodSummary | null {
  if (rows.length === 0) return null;

  const itemCount = rows.reduce((s, r) => s + r.item_count, 0);
  const totalPrice = rows.reduce((s, r) => s + r.total_price, 0);
  const snapshotDays = new Set(rows.map((r) => r.snapshot_date)).size;

  return {
    itemCount,
    avgPrice: itemCount > 0 ? Math.round((totalPrice / itemCount) * 100) / 100 : null,
    minPrice: Math.round(Math.min(...rows.map((r) => r.min_price)) * 100) / 100,
    maxPrice: Math.round(Math.max(...rows.map((r) => r.max_price)) * 100) / 100,
    snapshotDays,
  };
}
