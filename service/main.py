import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from agent.logging_config import configure_logging
from service.db import init_schema
from service.reviews_router import router as reviews_router
from service.webhooks.router import router as webhook_router

# load_dotenv() with no path searches from *this file's* directory upward,
# stopping at the first .env it finds -- since service/.env exists, an
# unqualified call would find that one and never reach the repo root's,
# silently dropping OPENAI_API_KEY/GITHUB_TOKEN. Load both by explicit path.
_SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(_SERVICE_DIR.parent / ".env")
load_dotenv(_SERVICE_DIR / ".env")

configure_logging()
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
