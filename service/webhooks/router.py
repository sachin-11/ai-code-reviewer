import json

from fastapi import APIRouter, Header, HTTPException, Request

from service.config import get_settings
from service.queue.base import InMemoryJobQueue
from service.webhooks.events import parse_pull_request_event, parse_review_comment_event
from service.webhooks.signature import verify_signature

router = APIRouter()
job_queue = InMemoryJobQueue()


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
            job_queue.enqueue("review_pr", event)
            return {"status": "queued", "job": "review_pr"}
        return {"status": "ignored"}

    if x_github_event == "pull_request_review_comment":
        event = parse_review_comment_event(payload)
        if event:
            job_queue.enqueue("handle_conversation", event)
            return {"status": "queued", "job": "handle_conversation"}
        return {"status": "ignored"}

    return {"status": "ignored"}
