from __future__ import annotations

from datetime import date

MAX_PAIRING_GAP_DAYS = 3


def nearest_snapshot_pair(
    anchor: date,
    candidates: list[date],
    *,
    max_gap_days: int = MAX_PAIRING_GAP_DAYS,
) -> date | None:
    """
    最近邻配对：日历差最小且 <= max_gap_days；平手取较早日期。
    无候选或最小差超过上限时返回 None。
    """
    if not candidates:
        return None

    best: date | None = None
    best_delta: int | None = None

    for d in candidates:
        delta = abs((d - anchor).days)
        if delta > max_gap_days:
            continue
        if best is None or delta < best_delta or (delta == best_delta and d < best):
            best = d
            best_delta = delta

    return best
