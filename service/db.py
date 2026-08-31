import os
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from service.config import get_settings

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@lru_cache
def _get_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool(
        settings.database_url,
        kwargs={"row_factory": dict_row},
        min_size=1,
        max_size=10,
        open=True,
    )


def get_connection():
    """A pooled connection, used the same way as psycopg.connect(): as a
    context manager (`with get_connection() as conn:`). Every caller
    previously opened and tore down its own TCP connection to Postgres --
    fine at this session's tiny test volume, but each `record_review`/
    `get_review_history`/etc. call would need its own connect+auth
    round-trip under any real traffic."""
    return _get_pool().connection()


def init_schema() -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        ddl = f.read()

    with get_connection() as conn:
        conn.execute(ddl)
        conn.commit()
