from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PgConnection

from src.config import ROOT, env


def get_connection() -> PgConnection:
    return psycopg2.connect(
        env("DATABASE_URL"),
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def connection_ok(conn: PgConnection) -> bool:
    if conn.closed:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except psycopg2.Error:
        return False


def ensure_connection(conn: PgConnection) -> PgConnection:
    if connection_ok(conn):
        return conn
    try:
        conn.close()
    except Exception:
        pass
    return get_connection()


@contextmanager
def db_session():
    """单次操作用同一连接（避免 Neon 连接池耗尽）。"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        conn.close()


def _run_sql_file(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with db_session() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            for stmt in statements:
                cur.execute(stmt)


def init_schema() -> None:
    _run_sql_file(ROOT / "sql" / "schema.sql")


def drop_legacy_tables() -> None:
    _run_sql_file(ROOT / "sql" / "drop_legacy.sql")
