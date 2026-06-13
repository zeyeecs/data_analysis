import { startOfDay, subDays } from "date-fns";
import type { DateRange } from "react-day-picker";

/** 以 end 为终点、向前推 days 天的区间（与概览默认 90 天算法一致） */
export function buildRecentDayRange(
  days: number,
  opts?: { minDate?: Date; maxDate?: Date },
): DateRange {
  const end = startOfDay(opts?.maxDate ?? new Date());
  let from = startOfDay(subDays(end, days));
  const min = opts?.minDate ? startOfDay(opts.minDate) : undefined;
  if (min && from < min) from = min;
  return { from, to: end };
}

export function isSameDateRange(a: DateRange | undefined, b: DateRange | undefined): boolean {
  if (!a?.from || !b?.from) return false;
  const aTo = startOfDay(a.to ?? a.from);
  const bTo = startOfDay(b.to ?? b.from);
  return (
    startOfDay(a.from).getTime() === startOfDay(b.from).getTime() &&
    aTo.getTime() === bTo.getTime()
  );
}

export const RECENT_DAY_SHORTCUTS = [7, 30, 90] as const;

export function toIsoDateString(value: Date | string | null | undefined): string | null {
  if (value == null) return null;
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) return null;
    return value.toISOString().slice(0, 10);
  }
  const raw = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}
