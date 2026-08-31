import base64
import json
import logging
import re
from datetime import datetime, timezone

from github import GithubException

from agent import github_client, pinecone_store

logger = logging.getLogger(__name__)

MEMORY_BRANCH = "ai-review-memory"
MEMORY_PATH = "memory.json"

FINGERPRINT_MARKER_RE = re.compile(
    r"<!-- ai-review-fp:([0-9a-f]+)\|\|\|(.*?)\|\|\|(.*?)\|\|\|(.*?) -->", re.DOTALL
)


def _empty_memory() -> dict:
    return {"dismissed_fingerprints": {}, "author_notes": {}}


def load_memory() -> dict:
    try:
        repo = github_client.get_repo()
        content_file = repo.get_contents(MEMORY_PATH, ref=MEMORY_BRANCH)
        data = json.loads(base64.b64decode(content_file.content).decode("utf-8"))
        data.setdefault("dismissed_fingerprints", {})
        data.setdefault("author_notes", {})
        return data
    except GithubException as exc:
        if exc.status != 404:
            logger.error("Failed to load memory: %s", exc)
        return _empty_memory()
    except Exception as exc:
        logger.error("Failed to load memory: %s", exc)
        return _empty_memory()


def _ensure_memory_branch(repo) -> None:
    try:
        repo.get_branch(MEMORY_BRANCH)
        return
    except GithubException as exc:
        if exc.status != 404:
            raise

    default_branch = repo.default_branch
    base_ref = repo.get_git_ref(f"heads/{default_branch}")
    repo.create_git_ref(ref=f"refs/heads/{MEMORY_BRANCH}", sha=base_ref.object.sha)


def save_memory(memory: dict) -> bool:
    try:
        repo = github_client.get_repo()
        _ensure_memory_branch(repo)

        content = json.dumps(memory, indent=2, sort_keys=True)

        try:
            existing = repo.get_contents(MEMORY_PATH, ref=MEMORY_BRANCH)
            repo.update_file(
                MEMORY_PATH, "Update AI review memory", content, existing.sha, branch=MEMORY_BRANCH
            )
        except GithubException as exc:
            if exc.status != 404:
                raise
            repo.create_file(MEMORY_PATH, "Initialize AI review memory", content, branch=MEMORY_BRANCH)

        return True
    except Exception as exc:
        logger.error("Failed to save memory: %s", exc)
        return False


def record_dismissal(memory: dict, fp: str, file: str, category: str, title: str, dismissed_by: str) -> None:
    now = datetime.now(timezone.utc).isoformat()

    memory["dismissed_fingerprints"][fp] = {
        "file": file,
        "category": category,
        "title": title,
        "dismissed_by": dismissed_by,
        "dismissed_at": now,
    }

    notes = memory["author_notes"].setdefault(dismissed_by, {"dismiss_counts": {}, "last_updated": None})
    notes["dismiss_counts"][category] = notes["dismiss_counts"].get(category, 0) + 1
    notes["last_updated"] = now

    if pinecone_store.is_enabled():
        pinecone_store.update_outcome(fp, "dismissed")


def parse_marker(body: str):
    match = FINGERPRINT_MARKER_RE.search(body or "")
    if not match:
        return None
    fp, file, category, title = match.groups()
    return {"fingerprint": fp, "file": file, "category": category, "title": title}


def scan_for_new_dismissals(pr, memory: dict) -> int:
    """Check the PR's existing bot review comments for thumbs-down reactions
    not yet recorded in memory, and record them in place."""
    new_count = 0

    try:
        comments = list(pr.get_review_comments())
    except Exception as exc:
        logger.error("Failed to fetch review comments for dismissal scan: %s", exc)
        return 0

    for comment in comments:
        parsed = parse_marker(comment.body)
        if not parsed or parsed["fingerprint"] in memory["dismissed_fingerprints"]:
            continue

        try:
            reactions = list(comment.get_reactions())
        except Exception as exc:
            logger.error("Failed to fetch reactions on comment %s: %s", comment.id, exc)
            continue

        thumbs_down = [r for r in reactions if r.content == "-1"]
        if not thumbs_down:
            continue

        reactor = thumbs_down[0].user.login if thumbs_down[0].user else "unknown"
        record_dismissal(
            memory, parsed["fingerprint"], parsed["file"], parsed["category"], parsed["title"], reactor
        )
        new_count += 1

    return new_count
