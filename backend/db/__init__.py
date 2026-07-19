"""
Shared PostgreSQL connection pool.
All modules that need DB access import `get_pool()` from here.
"""

import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL not configured")
        _pool = ConnectionPool(conninfo=url, min_size=2, max_size=10)
    return _pool
