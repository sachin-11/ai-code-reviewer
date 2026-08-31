from service.db import get_connection


def test_connections_are_reused_from_a_pool(postgres_conn):
    pids = []
    for _ in range(5):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid()")
                pids.append(cur.fetchone()["pg_backend_pid"])

    # A fresh psycopg.connect() per call would produce 5 distinct backend
    # PIDs (a new TCP connection + auth round-trip each time). Pooling
    # should reuse a small, stable set of backend connections instead.
    assert len(set(pids)) < 5
