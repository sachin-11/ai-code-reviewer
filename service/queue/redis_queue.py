from redis import Redis
from rq import Queue

from service.jobs import dispatch_job

DEFAULT_QUEUE_NAME = "ai-review"


class RedisJobQueue:
    def __init__(self, redis_url: str, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._redis = Redis.from_url(redis_url)
        self._queue = Queue(queue_name, connection=self._redis)

    def enqueue(self, job_type: str, payload: dict) -> None:
        self._queue.enqueue(dispatch_job, job_type, payload)
