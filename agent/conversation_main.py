import os
import sys
import traceback

from dotenv import load_dotenv

from agent.nodes.conversation import handle_comment

load_dotenv()

REQUIRED_ENV_VARS = [
    "GITHUB_TOKEN",
    "REPO_FULL_NAME",
    "PR_NUMBER",
    "COMMENT_ID",
    "COMMENT_AUTHOR",
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


def main() -> None:
    _check_env_vars()

    try:
        handle_comment(
            comment_id=int(os.environ["COMMENT_ID"]),
            comment_author=os.environ["COMMENT_AUTHOR"],
            pr_number=int(os.environ["PR_NUMBER"]),
            workspace=os.environ["WORKSPACE"],
        )
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
