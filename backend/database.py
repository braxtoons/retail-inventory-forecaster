import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from config import Config

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database', 'schema.sql')

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(1, 10, Config.DATABASE_URL, cursor_factory=RealDictCursor)
    return _pool


def reset_pool():
    """Close the pool so the next use reconnects (tests, forked evaluation workers)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def get_connection():
    """Borrow a pooled connection; commits on success, rolls back on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor():
    """Borrow a pooled connection and yield a RealDictCursor inside one transaction."""
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


def get_db_connection():
    """Unpooled connection for scripts (importers) that manage their own lifetime."""
    return psycopg2.connect(Config.DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Apply schema.sql (idempotent)."""
    with open(SCHEMA_PATH, 'r') as f:
        sql = f.read()
    with get_cursor() as cur:
        cur.execute(sql)
    print("Database initialized successfully!")


if __name__ == '__main__':
    init_db()
