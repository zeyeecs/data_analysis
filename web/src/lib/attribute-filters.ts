import { Prisma } from "@prisma/client";

/** 将库内以 / 分隔的属性值展开为下拉选项（去重、排序）。 */
export function expandSlashTokenOptions(values: string[]): string[] {
  const seen = new Set<string>();
  for (const value of values) {
    for (const part of value.split("/")) {
      const token = part.trim();
      if (token) seen.add(token);
    }
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b, "zh-CN"));
}

/** 多选包含匹配：字段值包含任一勾选值（OR，ILIKE）。 */
function containsListFilter(column: string, values: string[] | undefined): Prisma.Sql {
  const trimmed = values?.map((v) => v.trim()).filter(Boolean) ?? [];
  if (trimmed.length === 0) return Prisma.empty;
  const parts = trimmed.map(
    (v) => Prisma.sql`TRIM(${Prisma.raw(column)}) ILIKE ${`%${v}%`}`,
  );
  return Prisma.sql`(${Prisma.join(parts, " OR ")})`;
}

/** 多选排除匹配：字段值不包含任一勾选值（AND，NOT ILIKE）。 */
function excludesListFilter(column: string, values: string[] | undefined): Prisma.Sql {
  const trimmed = values?.map((v) => v.trim()).filter(Boolean) ?? [];
  if (trimmed.length === 0) return Prisma.empty;
  const parts = trimmed.map(
    (v) => Prisma.sql`COALESCE(TRIM(${Prisma.raw(column)}), '') NOT ILIKE ${`%${v}%`}`,
  );
  return Prisma.sql`(${Prisma.join(parts, " AND ")})`;
}

/** 多选颜色：字段值包含任一勾选值（OR）。如 blue/white 匹配 blue。 */
export function colorsFilterSql(values: string[] | undefined): Prisma.Sql {
  return containsListFilter("color", values);
}

export function colorsExcludeFilterSql(values: string[] | undefined): Prisma.Sql {
  return excludesListFilter("color", values);
}

/** 多选成色：字段值包含任一勾选值（OR）。 */
export function conditionsFilterSql(values: string[] | undefined): Prisma.Sql {
  return containsListFilter("condition", values);
}

export function conditionsExcludeFilterSql(values: string[] | undefined): Prisma.Sql {
  return excludesListFilter("condition", values);
}

/** 多选材质：字段值包含任一勾选值（OR）。 */
export function materialsFilterSql(values: string[] | undefined): Prisma.Sql {
  return containsListFilter("material", values);
}

export function materialsExcludeFilterSql(values: string[] | undefined): Prisma.Sql {
  return excludesListFilter("material", values);
}

/** 多选年份：字段值包含任一勾选值（OR）。 */
export function yearsFilterSql(values: string[] | undefined): Prisma.Sql {
  return containsListFilter("year", values);
}

export function yearsExcludeFilterSql(values: string[] | undefined): Prisma.Sql {
  return excludesListFilter("year", values);
}
