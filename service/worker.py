import os

from redis import Redis
from rq import Queue, Worker

from service.queue.redis_queue import DEFAULT_QUEUE_NAME


def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    conn = Redis.from_url(redis_url)
    queue = Queue(DEFAULT_QUEUE_NAME, connection=conn)
    worker = Worker([queue], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
