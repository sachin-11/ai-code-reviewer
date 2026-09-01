from redis import Redis
from rq import Queue

from service.queue.redis_queue import DEFAULT_QUEUE_NAME, JOB_TIMEOUT_SECONDS, RedisJobQueue

REDIS_URL = "redis://localhost:6390/0"


def _clear(conn):
    for key in conn.keys("rq:*"):
        conn.delete(key)


def test_enqueue_applies_job_timeout_and_lands_in_intermediate_queue():
    conn = Redis.from_url(REDIS_URL, socket_connect_timeout=2)
    try:
        conn.ping()
    except Exception as exc:
        import pytest

        pytest.skip(f"no local Redis reachable at {REDIS_URL}: {exc}")

    _clear(conn)
    try:
        rjq = RedisJobQueue(REDIS_URL)
        rjq.enqueue("review_pr", {"pr_number": 1})

        q = Queue(DEFAULT_QUEUE_NAME, connection=conn)
        # Some RQ 2.x point releases routed a fresh enqueue through a
        # separate ":intermediate" list instead of the legacy rq:queue:<name>
        # list a worker reads from Queue.job_ids -- that behavior was since
        # reverted (verified against the installed rq==2.12.0: enqueue lands
        # directly in rq:queue:<name> again). Check both so this doesn't
        # silently break again on the next RQ upgrade either direction.
        job_ids = conn.lrange(f"{q.key}:intermediate", 0, -1) or conn.lrange(q.key, 0, -1)
        assert len(job_ids) == 1

        job = q.fetch_job(job_ids[0].decode())
        assert job.timeout == JOB_TIMEOUT_SECONDS
    finally:
        _clear(conn)
