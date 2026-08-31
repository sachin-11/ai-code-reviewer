import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from rq import Queue, Worker

from service.db import init_schema
from service.queue.redis_queue import DEFAULT_QUEUE_NAME

# Repo-root .env (OPENAI_API_KEY, GITHUB_TOKEN, ...) plus service/.env
# (REDIS_URL, DATABASE_URL) -- load_dotenv() with no path only finds the
# former when run from the repo root.
load_dotenv()
load_dotenv(Path(__file__).parent / ".env")

REQUIRED_ENV_VARS = ["OPENAI_API_KEY", "GITHUB_TOKEN"]


def _check_env_vars() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    _check_env_vars()

    try:
        init_schema()
    except Exception as exc:
        print(f"[worker] failed to initialize database schema: {exc}", file=sys.stderr)

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    conn = Redis.from_url(redis_url)
    queue = Queue(DEFAULT_QUEUE_NAME, connection=conn)
    worker = Worker([queue], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
