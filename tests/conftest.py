import os

import psycopg
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://ai_reviewer:ai_reviewer@localhost:5442/ai_reviewer"
)


@pytest.fixture
def postgres_conn():
    """A real Postgres connection, skipping the test if none is reachable."""
    try:
        conn = psycopg.connect(TEST_DATABASE_URL, connect_timeout=2)
    except Exception as exc:
        pytest.skip(f"no local Postgres reachable at {TEST_DATABASE_URL}: {exc}")
    yield conn
    conn.close()
