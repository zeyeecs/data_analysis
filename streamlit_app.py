#!/usr/bin/env python3
"""按商品型号查看全渠道合并后的价格趋势（不区分店铺）。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import psycopg2

from src.analysis import (
    default_period_bounds,
    fetch_model_price_trend,
    fetch_table_bounds,
)
from src.config import load_config
from src.db import db_session

CACHE_TTL = 600

COLUMN_ZH: dict[str, str] = {
    "snapshot_date": "快照日期",
    "currency": "货币",
    "item_count": "样本件数",
    "avg_price": "均价",
    "min_price": "最低价",
    "max_price": "最高价",
    "median_price": "中位价",
    "total_price": "成交总额",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_table_bounds() -> dict[str, tuple[str | None, str | None]]:
    with db_session() as conn:
        raw = fetch_table_bounds(conn)
    return {
        tbl: (mn.isoformat() if mn else None, mx.isoformat() if mx else None)
        for tbl, (mn, mx) in raw.items()
    }


def _bounds_as_dates() -> dict[str, tuple[date | None, date | None]]:
    cached = _cached_table_bounds()
    out: dict[str, tuple[date | None, date | None]] = {}
    for tbl, (mn_s, mx_s) in cached.items():
        out[tbl] = (
            date.fromisoformat(mn_s) if mn_s else None,
            date.fromisoformat(mx_s) if mx_s else None,
        )
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner="正在加载价格趋势…")
def _cached_price_trend(
    start_iso: str,
    end_iso: str,
    model_key: str,
) -> pd.DataFrame:
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    with db_session() as conn:
        return fetch_model_price_trend(conn, start, end, model_key)


def _apply_chrome() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, [data-testid="stToolbar"] {visibility: hidden;}
        .stAppDeployButton {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _to_zh_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in COLUMN_ZH.items() if k in df.columns})


def _period_from_preset(
    bounds: dict[str, tuple[date | None, date | None]],
    days: int,
) -> tuple[date, date]:
    return default_period_bounds(bounds, days=days)


def _price_chart(trend: pd.DataFrame, currency: str | None = None) -> pd.DataFrame:
    df = trend if currency is None else trend[trend["currency"] == currency]
    if df.empty:
        return pd.DataFrame()
    out = df.set_index("snapshot_date")[["avg_price", "median_price", "min_price", "max_price"]]
    return out.sort_index().rename(
        columns={
            "avg_price": "均价",
            "median_price": "中位价",
            "min_price": "最低价",
            "max_price": "最高价",
        }
    )


def _period_summary(trend: pd.DataFrame) -> dict:
    if trend.empty:
        return {}
    items = int(trend["item_count"].sum())
    total = float(trend["total_price"].sum())
    return {
        "样本件数": items,
        "期间均价": round(total / items, 2) if items else None,
        "期间最低价": round(float(trend["min_price"].min()), 2),
        "期间最高价": round(float(trend["max_price"].max()), 2),
        "快照日数": int(trend["snapshot_date"].nunique()),
    }


load_config()
_apply_chrome()

st.set_page_config(
    page_title="商品价格趋势",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("商品价格趋势")
st.caption(
    "输入型号关键字，合并 F / R / V 全渠道已售样本，查看该商品的价格走势。"
    "不区分店铺；若含多种货币，按币种分别展示。"
)

if not (ROOT / "database.env").is_file():
    st.error("未找到 database.env，请先配置数据库连接。")
    st.stop()

try:
    with st.spinner("正在连接数据库…"):
        bounds = _bounds_as_dates()
except psycopg2.OperationalError as exc:
    st.error("无法连接数据库，请检查 database.env。")
    st.code(str(exc))
    st.stop()

default_start, default_end = default_period_bounds(bounds, days=30)

with st.sidebar:
    st.header("查询条件")
    preset = st.radio(
        "时间区间",
        ["30 天", "60 天", "90 天", "自定义"],
        index=0,
        horizontal=True,
    )
    if preset != "自定义":
        days = int(preset.split()[0])
        period_start, period_end = _period_from_preset(bounds, days)
    else:
        period_start, period_end = default_start, default_end
    c1, c2 = st.columns(2)
    period_start = c1.date_input("起始日", value=period_start)
    period_end = c2.date_input("结束日", value=period_end)
    if period_start > period_end:
        st.warning("起始日晚于结束日，查询时将自动对调。")

    model_filter = st.text_input(
        "型号关键字",
        "",
        help="必填。F/R 匹配 model，V 匹配 product_name；部分匹配、不区分大小写。",
    )

    if st.button("清除查询缓存", help="数据刚导入后点此刷新"):
        st.cache_data.clear()
        st.rerun()

model_key = model_filter.strip()

if not model_key:
    st.info("请在左侧输入 **型号关键字** 查看价格趋势。")
    st.stop()

ps, pe = min(period_start, period_end), max(period_start, period_end)

try:
    trend = _cached_price_trend(ps.isoformat(), pe.isoformat(), model_key)
except Exception as exc:
    st.error(f"查询失败：{exc}")
    st.stop()

if trend.empty:
    st.warning(f"在 {ps} ~ {pe} 内未找到匹配「{model_key}」的已售记录。")
    st.stop()

st.info(f"型号「{model_key}」· {ps} ~ {pe}")

summary = _period_summary(trend)
if summary:
    st.subheader("期间汇总")
    cols = st.columns(len(summary))
    for col, (label, val) in zip(cols, summary.items()):
        col.metric(label, val if val is not None else "—")

currencies = sorted(trend["currency"].dropna().unique().tolist())
if len(currencies) > 1:
    st.caption(f"含 {len(currencies)} 种货币（{', '.join(currencies)}），分开展示，请勿直接比较数值。")

for currency in currencies:
    subset = trend[trend["currency"] == currency]
    label = f"（{currency}）" if currency != "—" else ""
    st.subheader(f"价格趋势 {label}".strip())
    chart = _price_chart(subset)
    if not chart.empty:
        st.line_chart(chart)
    else:
        st.caption("无价格数据。")

st.subheader("日度明细")
st.dataframe(_to_zh_df(trend), use_container_width=True, hide_index=True)
