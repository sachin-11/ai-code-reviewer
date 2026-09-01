import os
import sys
import traceback

from dotenv import load_dotenv

from agent.graph import build_graph
from agent.logging_config import configure_logging
from agent.schemas import AgentState

load_dotenv()

REQUIRED_ENV_VARS = [
    "GITHUB_TOKEN",
    "PR_NUMBER",
    "PR_HEAD_SHA",
    "PR_BASE_SHA",
    "REPO_FULL_NAME",
    "HEAD_BRANCH",
    "BASE_BRANCH",
    "WORKSPACE",
]


def _check_env_vars() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    # OPENAI_API_KEY isn't needed when routing through Ollama instead (see
    # agent/llm_client.py) -- either one satisfies this check.
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OLLAMA_BASE_URL"):
        missing.append("OPENAI_API_KEY (or OLLAMA_BASE_URL)")
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def _build_initial_state() -> AgentState:
    return AgentState(
        pr_number=int(os.environ["PR_NUMBER"]),
        head_sha=os.environ["PR_HEAD_SHA"],
        base_sha=os.environ["PR_BASE_SHA"],
        repo_full_name=os.environ["REPO_FULL_NAME"],
        head_branch=os.environ["HEAD_BRANCH"],
        base_branch=os.environ["BASE_BRANCH"],
        workspace=os.environ["WORKSPACE"],
    )


def _extract(result, key: str):
    return result[key] if isinstance(result, dict) else getattr(result, key)


def main() -> None:
    _check_env_vars()
    configure_logging()

    try:
        initial_state = _build_initial_state()
        graph = build_graph()
        result = graph.invoke(initial_state)

        issues = _extract(result, "issues")
        verified_patches = _extract(result, "verified_patches")
        verified_count = sum(1 for patch in verified_patches if patch.verified)

        print(f"[main] {len(issues)} issue(s) found, {verified_count} patch(es) verified")
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
