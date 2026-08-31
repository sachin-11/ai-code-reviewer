from redis import Redis
from rq import Queue

from service.jobs import dispatch_job

DEFAULT_QUEUE_NAME = "ai-review"

# Generous ceiling so a real review (repo clone + up to 8 agentic
# tool-calling iterations + verify) isn't killed early on a large diff,
# while still bounding a genuinely hung job (stuck subprocess, network hang).
# Previously unset -- a hung job would block the worker (and every job
# behind it) indefinitely.
JOB_TIMEOUT_SECONDS = 600

# Deliberately not using RQ's retry=Retry(...): it routes the job through
# RQScheduler, which spawns its polling process via multiprocessing's "fork"
# context -- unavailable on Windows, where it silently falls back to
# "spawn" and was never verified to actually promote jobs out of the
# scheduled registry here (this exact worker already needed a Windows
# fallback once, for os.fork() in RQ's default Worker -- see worker.py).
# Whole-job retry also has a real side-effect risk: raise_fix_pr mints a
# new timestamped branch every call, so retrying a job that partially
# succeeded can leave more than one fix branch/PR behind. The OpenAI SDK
# already retries transient failures (rate limits, timeouts, 5xx) with
# max_retries=2 by default, which covers the highest-volume failure mode
# without any of the above.


class RedisJobQueue:
    def __init__(self, redis_url: str, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._redis = Redis.from_url(redis_url)
        self._queue = Queue(queue_name, connection=self._redis)

    def enqueue(self, job_type: str, payload: dict) -> None:
        self._queue.enqueue(
            dispatch_job,
            job_type,
            payload,
            job_timeout=JOB_TIMEOUT_SECONDS,
        )
