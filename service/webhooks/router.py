import json
from functools import lru_cache

from fastapi import APIRouter, Header, HTTPException, Request

from service.config import get_settings
from service.queue.base import InMemoryJobQueue
from service.queue.redis_queue import RedisJobQueue
from service.webhooks.events import parse_pull_request_event, parse_review_comment_event
from service.webhooks.signature import verify_signature

router = APIRouter()


@lru_cache
def get_job_queue():
    settings = get_settings()
    if settings.redis_url:
        return RedisJobQueue(settings.redis_url)
    return InMemoryJobQueue()


def _enqueue_or_503(job_type: str, event: dict) -> None:
    try:
        get_job_queue().enqueue(job_type, event)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"failed to enqueue job: {exc}")


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    settings = get_settings()
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=500, detail="server misconfigured: GITHUB_WEBHOOK_SECRET not set")

    body = await request.body()
    if not verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON payload")

    if x_github_event == "pull_request":
        event = parse_pull_request_event(payload)
        if event:
            _enqueue_or_503("review_pr", event)
            return {"status": "queued", "job": "review_pr"}
        return {"status": "ignored"}

    if x_github_event == "pull_request_review_comment":
        event = parse_review_comment_event(payload)
        if event:
            _enqueue_or_503("handle_conversation", event)
            return {"status": "queued", "job": "handle_conversation"}
        return {"status": "ignored"}

    return {"status": "ignored"}
