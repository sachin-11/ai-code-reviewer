import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from service.db import init_schema
from service.reviews_router import router as reviews_router
from service.webhooks.router import router as webhook_router

# Repo-root .env (OPENAI_API_KEY, GITHUB_TOKEN, ...) plus service/.env
# (GITHUB_WEBHOOK_SECRET, REDIS_URL, DATABASE_URL) -- load_dotenv() with no
# path only finds the former when run from the repo root.
load_dotenv()
load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_schema()
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)
    yield


app = FastAPI(title="AI Code Reviewer Webhook Service", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(reviews_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
