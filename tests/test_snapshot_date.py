from datetime import date

from src.snapshot_date import parse_snapshot_date


def test_chinese_date_in_filename():
    assert parse_snapshot_date("2025年3月1日-f.xlsx") == date(2025, 3, 1)


def test_underscore_yyyymmdd():
    assert parse_snapshot_date("sold_items_20250301_export.xlsx") == date(2025, 3, 1)


def test_unparseable_returns_none():
    assert parse_snapshot_date("inventory.xlsx") is None
