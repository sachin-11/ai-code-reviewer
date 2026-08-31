from typing import Optional

HANDLED_PR_ACTIONS = {"opened", "synchronize", "reopened"}


def parse_pull_request_event(payload: dict) -> Optional[dict]:
    if payload.get("action") not in HANDLED_PR_ACTIONS:
        return None

    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    head = pr.get("head") or {}
    base = pr.get("base") or {}

    return {
        "pr_number": pr.get("number"),
        "head_sha": head.get("sha"),
        "base_sha": base.get("sha"),
        "head_branch": head.get("ref"),
        "base_branch": base.get("ref"),
        "repo_full_name": repo.get("full_name"),
    }


def parse_review_comment_event(payload: dict) -> Optional[dict]:
    if payload.get("action") != "created":
        return None

    comment = payload.get("comment") or {}
    if comment.get("in_reply_to_id") is None:
        return None

    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    user = comment.get("user") or {}

    return {
        "pr_number": pr.get("number"),
        "comment_id": comment.get("id"),
        "comment_author": user.get("login"),
        "repo_full_name": repo.get("full_name"),
    }
