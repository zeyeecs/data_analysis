from __future__ import annotations

from src.xlsx_import import build_old_data, prepare_import_record


def test_build_old_data_fr_keeps_raw_model() -> None:
    record = {
        "item_id": "123",
        "brand": "Louis Vuitton",
        "model": "Speedy Bandouliere 25 Monogram Canvas",
        "condition": "Excellent",
        "color": "Brown",
        "price": 1000,
        "material": None,
    }
    old_data = build_old_data(record, "F")
    assert old_data["model"] == "Speedy Bandouliere 25 Monogram Canvas"
    assert old_data["brand"] == "Louis Vuitton"
    assert old_data["price"] == "1000"


def test_prepare_import_record_clears_model_fields() -> None:
    record = {
        "item_id": "123",
        "brand": "Louis Vuitton",
        "model": "Speedy Bandouliere 25 Monogram Canvas",
        "condition": "Excellent",
        "color": "Brown",
        "price": 1000,
        "material": "Canvas",
        "year": "2020",
        "other": "sellier",
    }
    prepare_import_record(record, "F")
    assert record["brand"] == "louis vuitton"
    assert record["model"] is None
    assert record["material"] is None
    assert record["year"] is None
    assert record["other"] is None
    assert record["condition"] == "99新/Excellent"
    assert record["color"] == "brown"


def test_prepare_import_record_v_clears_product_name() -> None:
    record = {
        "item_id": "456",
        "brand": "Gucci",
        "product_name": "GG Marmont leather handbag",
        "material": "Leather",
        "color": "Black",
        "condition": "Excellent",
        "price": 500,
        "year": None,
        "other": None,
    }
    prepare_import_record(record, "V")
    assert record["product_name"] is None
    assert record["material"] == "Leather"
    assert record["brand"] == "gucci"
