import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from agent import github_client
from agent.fingerprint import fingerprint as compute_fingerprint
from agent.graph import build_graph
from agent.llm_client import tracing_enabled
from agent.nodes import fix_pr_decision
from agent.nodes.conversation import handle_comment
from agent.schemas import AgentState
from service import reviews_repo
from service.workspace import cleanup_workspace, clone_workspace

logger = logging.getLogger(__name__)

# Fraction of completed reviews with at least one issue that get sampled for
# online eval (an LLM judge grades each finding's plausibility against the
# diff, no ground truth needed). Independent of the offline golden-dataset
# eval -- this catches drift on real, unscripted PRs the golden dataset
# doesn't cover.
ONLINE_EVAL_SAMPLE_RATE = float(os.environ.get("ONLINE_EVAL_SAMPLE_RATE", "0.15"))

# Circuit breaker on total OpenAI spend across every repo this deployment
# reviews (one shared bill) -- independent of agentic_analyze's
# MAX_COST_PER_REVIEW_USD, which only bounds a single review's own spend.
DAILY_COST_CAP_USD = float(os.environ.get("DAILY_COST_CAP_USD", "5.0"))


def _extract(result, key: str):
    return result[key] if isinstance(result, dict) else getattr(result, key)


def _get_trace_url(run_id: str) -> Optional[str]:
    # Best-effort: LangSmith flushes traces asynchronously, so the run may
    # not be readable yet immediately after invoke() returns.
    if not tracing_enabled():
        return None

    try:
        from langsmith import Client

        client = Client()
        run = client.read_run(run_id)
        return client.get_run_url(run=run)
    except Exception as exc:
        logger.error("Could not fetch LangSmith trace URL for run %s: %s", run_id, exc)
        return None


def _get_node_latencies(run_id: str) -> dict:
    # Best-effort, same caveat as _get_trace_url: LangSmith flushes
    # asynchronously, so the child runs may not all be readable yet.
    # read_run(load_child_runs=True) is deprecated (removal after Jan 2027)
    # in favor of runs.retrieve(), which has no equivalent one-call
    # child-tree fetch -- reconstructing it via runs.query() + trace_id
    # would need a second round trip for no benefit here.
    if not tracing_enabled():
        return {}

    try:
        from langsmith import Client

        client = Client()
        run = client.read_run(run_id, load_child_runs=True)
        return {
            child.name: (child.end_time - child.start_time).total_seconds()
            for child in (run.child_runs or [])
            if child.end_time
        }
    except Exception as exc:
        logger.error("Could not fetch LangSmith node latencies for run %s: %s", run_id, exc)
        return {}


def _record_review_history(
    payload: dict,
    final_state,
    trace_url: Optional[str],
    latency_seconds: float,
    node_latencies: dict,
) -> Optional[int]:
    try:
        issues = _extract(final_state, "issues")
        verified_patches = _extract(final_state, "verified_patches")
        fix_pr_url = _extract(final_state, "fix_pr_url")
        cost_usd = _extract(final_state, "cost_usd")
        iteration_count = _extract(final_state, "iteration_count")
        hit_max_iterations = _extract(final_state, "hit_max_iterations")
        hit_cost_cap = _extract(final_state, "hit_cost_cap")

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

        return reviews_repo.record_review(
            payload["repo_full_name"],
            payload["pr_number"],
            payload["head_sha"],
            payload["base_sha"],
            issue_dicts,
            verified_count,
            fix_pr_url,
            summary=None,
            cost_usd=cost_usd,
            trace_url=trace_url,
            latency_seconds=latency_seconds,
            iteration_count=iteration_count,
            hit_max_iterations=hit_max_iterations,
            hit_cost_cap=hit_cost_cap,
            node_latencies=node_latencies,
        )
    except Exception as exc:
        logger.error("Failed to record review history: %s", exc)
        return None


def _daily_cost_cap_exceeded() -> bool:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        return reviews_repo.get_total_cost_since(since) >= DAILY_COST_CAP_USD
    except Exception as exc:
        logger.error("Could not check daily cost cap, failing open: %s", exc)
        return False


def _maybe_sample_for_eval(review_id: Optional[int], diff: str, issues: list) -> None:
    if review_id is None or not issues:
        return
    if random.random() > ONLINE_EVAL_SAMPLE_RATE:
        return

    try:
        from eval.judge import judge_online_sample

        verdict = judge_online_sample(diff, issues)
        results = verdict.get("results", [])
        valid = sum(1 for r in results if r.get("status") == "valid")
        reviews_repo.record_eval_sample(review_id, len(results), valid, verdict)
        logger.info("Online eval sampled review %s: %s/%s valid", review_id, valid, len(results))
    except Exception as exc:
        logger.error("Online eval sampling failed for review %s: %s", review_id, exc)


def handle_review_pr(payload: dict) -> None:
    repo_full_name = payload["repo_full_name"]
    head_sha = payload["head_sha"]

    # Safe because RQ's default Worker processes one job at a time per
    # process; agent.github_client reads routing/auth from process env vars
    # (carried over from its original CI-script design), so this only needs
    # to be correct for the duration of this job.
    os.environ["REPO_FULL_NAME"] = repo_full_name

    if _daily_cost_cap_exceeded():
        logger.warning(
            "Daily cost cap ($%.2f) reached, skipping review for %s#%s",
            DAILY_COST_CAP_USD, repo_full_name, payload["pr_number"],
        )
        github_client.post_pr_comment(
            payload["pr_number"],
            f"⚠️ Automated review skipped: the daily cost cap (${DAILY_COST_CAP_USD:.2f}) "
            "has been reached across all repos. It will resume automatically once usage "
            "rolls off in the next 24 hours.",
        )
        return

    github_token = github_client.get_git_auth_token(repo_full_name)
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
        run_id = str(uuid.uuid4())
        started_at = time.time()
        final_state = build_graph().invoke(
            state,
            config={
                "run_id": run_id,
                "tags": ["review_pr"],
                "metadata": {"repo_full_name": repo_full_name, "pr_number": payload["pr_number"]},
            },
        )
        latency_seconds = time.time() - started_at
        trace_url = _get_trace_url(run_id)
        node_latencies = _get_node_latencies(run_id)
        review_id = _record_review_history(
            payload, final_state, trace_url, latency_seconds, node_latencies
        )
        _maybe_sample_for_eval(review_id, _extract(final_state, "diff"), _extract(final_state, "issues"))
    finally:
        cleanup_workspace(workspace)


def handle_conversation(payload: dict) -> None:
    repo_full_name = payload["repo_full_name"]
    head_sha = payload["head_sha"]

    os.environ["REPO_FULL_NAME"] = repo_full_name

    github_token = github_client.get_git_auth_token(repo_full_name)
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


def handle_fix_pr_decision(payload: dict) -> None:
    os.environ["REPO_FULL_NAME"] = payload["repo_full_name"]
    fix_pr_decision.handle_fix_pr_decision(
        pr_number=payload["pr_number"],
        decision=payload["decision"],
        comment_author=payload["comment_author"],
    )


JOB_HANDLERS = {
    "review_pr": handle_review_pr,
    "handle_conversation": handle_conversation,
    "fix_pr_decision": handle_fix_pr_decision,
}


def dispatch_job(job_type: str, payload: dict) -> None:
    handler = JOB_HANDLERS.get(job_type)
    if handler is None:
        logger.error("No handler registered for job type: %s", job_type)
        return
    handler(payload)
