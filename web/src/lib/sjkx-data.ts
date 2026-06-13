import "@/lib/load-database-env";

import type { ShopTotals } from "@/data/schema";
import { isTransientDbError } from "@/lib/database-url";
import { toIsoDateString } from "@/lib/dates";
import { prisma } from "@/lib/prisma";

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

type ShopCountRow = { shop: string; row_count: bigint | number };
type SnapshotBoundsRow = { min_date: Date | string | null; max_date: Date | string | null };

export async function fetchDashboardData(): Promise<{ shops: ShopTotals }> {
  return withDbRetry(async () => fetchDashboardDataOnce());
}

async function fetchDashboardDataOnce(): Promise<{ shops: ShopTotals }> {
  const [shopRows, boundsRows] = await Promise.all([
    prisma.$queryRaw<ShopCountRow[]>`
      SELECT 'F' AS shop, COUNT(*)::bigint AS row_count FROM "F"
      UNION ALL
      SELECT 'R', COUNT(*)::bigint FROM "R"
      UNION ALL
      SELECT 'V', COUNT(*)::bigint FROM "V"
    `,
    prisma.$queryRaw<SnapshotBoundsRow[]>`
      SELECT MIN(d) AS min_date, MAX(d) AS max_date
      FROM (
        SELECT snapshot_date AS d FROM "F" WHERE snapshot_date IS NOT NULL
        UNION ALL
        SELECT snapshot_date FROM "R" WHERE snapshot_date IS NOT NULL
        UNION ALL
        SELECT snapshot_date FROM "V" WHERE snapshot_date IS NOT NULL
      ) t
    `,
  ]);

  const counts = { F: 0, R: 0, V: 0 };
  for (const row of shopRows) {
    const key = row.shop as keyof typeof counts;
    if (key in counts) counts[key] = Number(row.row_count);
  }

  const bounds = boundsRows[0];

  return {
    shops: {
      ...counts,
      total: counts.F + counts.R + counts.V,
      snapshotDates: {
        min: toIsoDateString(bounds?.min_date ?? null),
        max: toIsoDateString(bounds?.max_date ?? null),
      },
    },
  };
}
