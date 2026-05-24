from datetime import date

from scripts.import_to_tables import filter_items_for_import


def _item(name: str) -> dict:
    return {"name": name, "token": "t"}


def test_skip_existing_snapshot_date():
    items = [_item("2026年05月01日14：26-f.xlsx"), _item("2026年05月02日14：18-f.xlsx")]
    existing = {date(2026, 5, 1)}
    to_import, skipped = filter_items_for_import(
        items, existing, False, skip_existing=True
    )
    assert len(to_import) == 1
    assert to_import[0]["name"].startswith("2026年05月02日")
    assert skipped == 1


def test_same_batch_duplicate_snapshot_date():
    items = [
        _item("2026年05月01日14：26-f.xlsx"),
        _item("2026年05月01日20：00-f.xlsx"),
    ]
    to_import, skipped = filter_items_for_import(
        items, set(), False, skip_existing=True
    )
    assert len(to_import) == 1
    assert skipped == 1


def test_reimport_all_does_not_skip_existing():
    items = [_item("2026年05月01日14：26-f.xlsx")]
    existing = {date(2026, 5, 1)}
    to_import, skipped = filter_items_for_import(
        items, existing, False, skip_existing=False
    )
    assert len(to_import) == 1
    assert skipped == 0


def test_skip_null_snapshot_bucket():
    items = [_item("inventory.xlsx")]
    to_import, skipped = filter_items_for_import(
        items, set(), True, skip_existing=True
    )
    assert to_import == []
    assert skipped == 1
