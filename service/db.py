import os

import psycopg
from psycopg.rows import dict_row

from service.config import get_settings

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection():
    settings = get_settings()
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def init_schema() -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        ddl = f.read()

    with get_connection() as conn:
        conn.execute(ddl)
        conn.commit()
