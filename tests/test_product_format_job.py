from __future__ import annotations

from datetime import date

from src.product_format_job import _snapshot_filter_clause


def test_snapshot_filter_none_means_all_rows() -> None:
    clause, params = _snapshot_filter_clause(None)
    assert clause == ""
    assert params == []


def test_snapshot_filter_single_date() -> None:
    clause, params = _snapshot_filter_clause([date(2026, 5, 1)])
    assert clause == " AND snapshot_date IN (%s)"
    assert params == [date(2026, 5, 1)]


def test_snapshot_filter_null_bucket() -> None:
    clause, params = _snapshot_filter_clause([None])
    assert clause == " AND snapshot_date IS NULL"
    assert params == []


def test_snapshot_filter_mixed_dates_and_null() -> None:
    clause, params = _snapshot_filter_clause([date(2026, 5, 2), None, date(2026, 5, 1)])
    assert clause == " AND (snapshot_date IN (%s, %s) OR snapshot_date IS NULL)"
    assert params == [date(2026, 5, 1), date(2026, 5, 2)]
