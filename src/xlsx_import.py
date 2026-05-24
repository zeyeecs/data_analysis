from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

from openpyxl import load_workbook

from src.snapshot_date import parse_snapshot_date

# F / R 表头映射（价格列名随汇率变化）
FR_FIELD_MAP = {
    "id": "item_id",
    "品牌": "brand",
    "型号": "model",
    "成色": "condition",
    "颜色": "color",
    "图片路径": "image_path",
    "所有图片网址": "image_urls",
}

V_FIELD_MAP = {
    "图片": "image",
    "id": "item_id",
    "品牌": "brand",
    "商品名称": "product_name",
    "材质": "material",
    "颜色": "color",
    "尺寸": "size",
    "价格": "price",
    "货币": "currency",
    "卖家价格": "seller_price",
    "买家手续费": "buyer_fee",
    "点赞数": "likes",
    "上架时间": "listed_at",
    "售出时间": "sold_at",
    "成色": "condition",
    "链接": "url",
}

FR_COLUMNS = [
    "item_id",
    "brand",
    "model",
    "condition",
    "price",
    "color",
    "image_path",
    "image_urls",
    "snapshot_date",
]

def clear_image_fields(record: dict[str, Any], table_kind: str) -> None:
    """入库前清空图片相关列（后续可单独补 R2 URL）。"""
    if table_kind in {"F", "R"}:
        record["image_path"] = None
        record["image_urls"] = None
    elif table_kind == "V":
        record["image"] = None


V_COLUMNS = [
    "image",
    "item_id",
    "brand",
    "product_name",
    "material",
    "color",
    "size",
    "price",
    "currency",
    "seller_price",
    "buyer_fee",
    "likes",
    "listed_at",
    "sold_at",
    "condition",
    "url",
    "snapshot_date",
]


def _normalize_header(cell: Any) -> str | None:
    if cell is None:
        return None
    text = str(cell).strip()
    if not text:
        return None
    upper = text.upper()
    if upper == "ID":
        return "item_id"
    if "价格" in text:
        return "price"
    return FR_FIELD_MAP.get(text) or V_FIELD_MAP.get(text) or V_FIELD_MAP.get(text.lower())


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _to_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _row_to_fr(values: tuple[Any, ...], header_map: list[str | None], snapshot: date | None) -> dict[str, Any] | None:
    row: dict[str, Any] = {col: None for col in FR_COLUMNS}
    empty = True
    for idx, field in enumerate(header_map):
        if field is None or idx >= len(values):
            continue
        val = values[idx]
        if val is not None and str(val).strip() != "":
            empty = False
        if field == "item_id":
            row[field] = _to_str(val)
        elif field == "price":
            row[field] = _to_decimal(val)
        else:
            row[field] = _to_str(val)
    if empty or not row.get("item_id"):
        return None
    row["snapshot_date"] = snapshot
    return row


def _row_to_v(values: tuple[Any, ...], header_map: list[str | None], snapshot: date | None) -> dict[str, Any] | None:
    row: dict[str, Any] = {col: None for col in V_COLUMNS}
    empty = True
    for idx, field in enumerate(header_map):
        if field is None or idx >= len(values):
            continue
        val = values[idx]
        if val is not None and str(val).strip() != "":
            empty = False
        if field == "item_id":
            row[field] = _to_str(val)
        elif field in {"price", "seller_price", "buyer_fee"}:
            row[field] = _to_decimal(val)
        elif field == "likes":
            row[field] = _to_int(val)
        elif field in {"listed_at", "sold_at"}:
            row[field] = _to_ts(val)
        else:
            row[field] = _to_str(val)
    if empty or not row.get("item_id"):
        return None
    row["snapshot_date"] = snapshot
    return row


def iter_sheet_rows(
    content: bytes,
    *,
    table_kind: str,
    snapshot_date: date | None,
) -> Iterator[dict[str, Any]]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows_iter = ws.iter_rows(values_only=True)
        header_cells = next(rows_iter, None)
        if not header_cells:
            return
        header_map = [_normalize_header(c) for c in header_cells]

        convert = _row_to_fr if table_kind in {"F", "R"} else _row_to_v
        for values in rows_iter:
            if not values:
                continue
            record = convert(values, header_map, snapshot_date)
            if record:
                yield record
    finally:
        wb.close()
