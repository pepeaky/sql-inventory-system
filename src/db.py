from contextlib import contextmanager

import psycopg2
from psycopg2 import pool, extras

from src.config import get_db_config, get_pool_config

_pool: pool.ThreadedConnectionPool | None = None


def init_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        db = get_db_config()
        p = get_pool_config()
        _pool = pool.ThreadedConnectionPool(p["minconn"], p["maxconn"], **db)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_connection():
    p = init_pool()
    conn = p.getconn()
    try:
        yield conn
    finally:
        p.putconn(conn)


@contextmanager
def transaction():
    """Yields (conn, cursor) inside an atomic transaction."""
    with get_connection() as conn:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)
        try:
            yield conn, cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def execute_schema(schema_path: str) -> None:
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            with open(schema_path) as f:
                cur.execute(f.read())
