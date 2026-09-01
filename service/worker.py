import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from rq import Queue, SimpleWorker, Worker

from service.db import init_schema
from service.queue.redis_queue import DEFAULT_QUEUE_NAME

# load_dotenv() with no path searches from *this file's* directory upward,
# stopping at the first .env it finds -- since service/.env exists, an
# unqualified call would find that one and never reach the repo root's,
# silently dropping OPENAI_API_KEY/GITHUB_TOKEN. Load both by explicit path.
_SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(_SERVICE_DIR.parent / ".env")
load_dotenv(_SERVICE_DIR / ".env")

REQUIRED_ENV_VARS = ["GITHUB_TOKEN"]


def _check_env_vars() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    # OPENAI_API_KEY isn't needed when routing through Ollama instead (see
    # agent/llm_client.py) -- either one satisfies this check.
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OLLAMA_BASE_URL"):
        missing.append("OPENAI_API_KEY (or OLLAMA_BASE_URL)")
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

    # RQ's default Worker forks a child process per job via os.fork(), which
    # doesn't exist on Windows. SimpleWorker runs jobs in-process instead.
    worker_class = SimpleWorker if platform.system() == "Windows" else Worker
    worker = worker_class([queue], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
