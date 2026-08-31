import logging

logger = logging.getLogger(__name__)


def handle_review_pr(payload: dict) -> None:
    print(f"[worker] review_pr job received for PR #{payload.get('pr_number')} in {payload.get('repo_full_name')}")
    print("[worker] TODO: wire into the ReAct agent loop (next module)")


def handle_conversation(payload: dict) -> None:
    print(
        f"[worker] handle_conversation job received for comment {payload.get('comment_id')} "
        f"in {payload.get('repo_full_name')}"
    )
    print("[worker] TODO: wire into the ReAct agent loop (next module)")


JOB_HANDLERS = {
    "review_pr": handle_review_pr,
    "handle_conversation": handle_conversation,
}


def dispatch_job(job_type: str, payload: dict) -> None:
    handler = JOB_HANDLERS.get(job_type)
    if handler is None:
        logger.error("No handler registered for job type: %s", job_type)
        return
    handler(payload)
