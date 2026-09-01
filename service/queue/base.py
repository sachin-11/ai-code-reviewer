import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: dict) -> None: ...


class InMemoryJobQueue:
    """Placeholder queue for local development before the Redis-backed queue
    (a later module) is wired in. Jobs are kept in memory and logged, not
    persisted or processed by a worker."""

    def __init__(self) -> None:
        self.jobs: list[dict] = []

    def enqueue(self, job_type: str, payload: dict) -> None:
        job = {"type": job_type, "payload": payload}
        self.jobs.append(job)
        logger.info("[queue:stub] enqueued %s: pr=%s", job_type, payload.get("pr_number"))
