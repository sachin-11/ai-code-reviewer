import logging
import os

from agent.fingerprint import fingerprint as compute_fingerprint
from agent.graph import build_graph
from agent.nodes.conversation import handle_comment
from agent.schemas import AgentState
from service import reviews_repo
from service.workspace import cleanup_workspace, clone_workspace

logger = logging.getLogger(__name__)


def _extract(result, key: str):
    return result[key] if isinstance(result, dict) else getattr(result, key)


def _record_review_history(payload: dict, final_state) -> None:
    try:
        issues = _extract(final_state, "issues")
        verified_patches = _extract(final_state, "verified_patches")
        fix_pr_url = _extract(final_state, "fix_pr_url")

        verified_count = sum(1 for p in verified_patches if p.verified)
        issue_dicts = [
            {
                "fingerprint": compute_fingerprint(issue.file, issue.category.value, issue.title),
                "file": issue.file,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "title": issue.title,
                "confidence": issue.confidence,
                "fixable": issue.fixable,
            }
            for issue in issues
        ]

        reviews_repo.record_review(
            payload["repo_full_name"],
            payload["pr_number"],
            payload["head_sha"],
            payload["base_sha"],
            issue_dicts,
            verified_count,
            fix_pr_url,
            summary=None,
        )
    except Exception as exc:
        logger.error("Failed to record review history: %s", exc)


def handle_review_pr(payload: dict) -> None:
    repo_full_name = payload["repo_full_name"]
    head_sha = payload["head_sha"]

    # Safe because RQ's default Worker processes one job at a time per
    # process; agent.github_client reads routing/auth from process env vars
    # (carried over from its original CI-script design), so this only needs
    # to be correct for the duration of this job.
    os.environ["REPO_FULL_NAME"] = repo_full_name

    github_token = os.environ["GITHUB_TOKEN"]
    workspace = clone_workspace(repo_full_name, head_sha, github_token)

    try:
        state = AgentState(
            pr_number=payload["pr_number"],
            head_sha=head_sha,
            base_sha=payload["base_sha"],
            head_branch=payload["head_branch"],
            base_branch=payload["base_branch"],
            repo_full_name=repo_full_name,
            workspace=workspace,
        )
        final_state = build_graph().invoke(state)
        _record_review_history(payload, final_state)
    finally:
        cleanup_workspace(workspace)


def handle_conversation(payload: dict) -> None:
    repo_full_name = payload["repo_full_name"]
    head_sha = payload["head_sha"]

    os.environ["REPO_FULL_NAME"] = repo_full_name

    github_token = os.environ["GITHUB_TOKEN"]
    workspace = clone_workspace(repo_full_name, head_sha, github_token)

    try:
        handle_comment(
            comment_id=payload["comment_id"],
            comment_author=payload["comment_author"],
            pr_number=payload["pr_number"],
            workspace=workspace,
        )
    finally:
        cleanup_workspace(workspace)


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
