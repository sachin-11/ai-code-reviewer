from typing import Protocol


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
        print(f"[queue:stub] enqueued {job_type}: pr={payload.get('pr_number')}")
