import logging
import os
import subprocess
import time
from typing import Optional

from github import Auth, Github
from github.Repository import Repository

from agent.fingerprint import fingerprint as compute_fingerprint
from agent.schemas import Issue, Patch, Severity

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx")

SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
}

SUMMARY_MARKER = "<!-- ai-code-reviewer:summary -->"
FIX_PR_MARKER = "<!-- ai-code-reviewer:fix-pr -->"

MIN_COMMENT_CONFIDENCE = 0.6
POST_DELAY_SECONDS = 0.5

FIX_COMMIT_NAME = "ai-code-reviewer[bot]"
FIX_COMMIT_EMAIL = "ai-code-reviewer[bot]@users.noreply.github.com"

FIX_PR_MERGE_METHOD = "squash"

FIX_PR_APPROVAL_PROMPT = (
    "This fix PR was generated automatically and has not been merged yet.\n\n"
    "Reply **approve** on this thread to merge it, or **reject** to close it "
    "without merging. Only users with write access to this repository can do "
    "either."
)


MAX_THREAD_HOPS = 10


def get_client() -> Github:
    token = os.environ["GITHUB_TOKEN"]
    return Github(auth=Auth.Token(token))


def get_authenticated_login() -> Optional[str]:
    try:
        return get_client().get_user().login
    except Exception as exc:
        logger.error("Failed to fetch authenticated user login: %s", exc)
        return None


def get_review_comment(comment_id: int, pr_number: int):
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        return pr.get_review_comment(comment_id)
    except Exception as exc:
        logger.error("Failed to fetch review comment %s: %s", comment_id, exc)
        return None


def get_thread_root(comment, pr_number: int):
    current = comment
    hops = 0
    while current.in_reply_to_id and hops < MAX_THREAD_HOPS:
        parent = get_review_comment(current.in_reply_to_id, pr_number)
        if parent is None:
            return None
        current = parent
        hops += 1
    return current


def reply_to_review_comment(pr_number: int, comment_id: int, body: str) -> bool:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        pr.create_review_comment_reply(comment_id, body)
        return True
    except Exception as exc:
        logger.error("Failed to reply to comment %s: %s", comment_id, exc)
        return False


def get_repo() -> Repository:
    repo_full_name = os.environ["REPO_FULL_NAME"]
    return get_client().get_repo(repo_full_name)


def fetch_diff(base_sha: str, head_sha: str, workspace: str) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", base_sha, head_sha, "--unified=5", "--no-color"],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to fetch diff %s..%s: %s", base_sha, head_sha, exc.stderr)
        return ""


def fetch_changed_files(base_sha: str, head_sha: str, workspace: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_sha, head_sha],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to fetch changed files %s..%s: %s", base_sha, head_sha, exc.stderr)
        return []

    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [f for f in files if f.endswith(ALLOWED_EXTENSIONS)]


def fetch_file_content(filepath: str, workspace: str) -> str:
    try:
        with open(os.path.join(workspace, filepath), "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        logger.error("Failed to read %s: %s", filepath, exc)
        return ""


def _format_issue_comment(issue: Issue) -> str:
    emoji = SEVERITY_EMOJI[issue.severity]
    fp = compute_fingerprint(issue.file, issue.category.value, issue.title)
    return (
        f"{emoji} **{issue.severity.value.upper()} · {issue.category.value}**\n\n"
        f"**{issue.title}**\n\n"
        f"{issue.description}\n\n"
        f"**Suggestion:** {issue.suggestion}\n\n"
        f"<!-- ai-review-fp:{fp}|||{issue.file}|||{issue.category.value}|||{issue.title} -->"
    )


def post_review_comments(issues: list[Issue], head_sha: str, pr_number: int) -> None:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
    except Exception as exc:
        logger.error("Failed to fetch PR #%s: %s", pr_number, exc)
        return

    try:
        commit = repo.get_commit(head_sha)
    except Exception as exc:
        logger.error("Failed to fetch commit %s: %s", head_sha, exc)
        return

    try:
        existing_bodies = {c.body for c in pr.get_review_comments()}
    except Exception as exc:
        logger.error("Failed to fetch existing review comments: %s", exc)
        existing_bodies = set()

    for issue in issues:
        if issue.confidence < MIN_COMMENT_CONFIDENCE:
            continue

        body = _format_issue_comment(issue)
        if body in existing_bodies:
            continue

        try:
            pr.create_review_comment(
                body=body,
                commit=commit,
                path=issue.file,
                line=issue.line_end,
            )
        except Exception as exc:
            logger.error(
                "Failed to post review comment on %s:%s: %s", issue.file, issue.line_end, exc
            )

        time.sleep(POST_DELAY_SECONDS)


def post_summary_comment(
    summary: str, issues: list[Issue], fix_pr_url: Optional[str], pr_number: int
) -> None:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
    except Exception as exc:
        logger.error("Failed to fetch PR #%s: %s", pr_number, exc)
        return

    try:
        for comment in pr.get_issue_comments():
            if SUMMARY_MARKER in comment.body:
                comment.delete()
                break
    except Exception as exc:
        logger.error("Failed to delete previous summary comment: %s", exc)

    counts = {severity: 0 for severity in Severity}
    for issue in issues:
        counts[issue.severity] += 1

    table_lines = ["| Severity | Count |", "| --- | --- |"]
    for severity in Severity:
        table_lines.append(
            f"| {SEVERITY_EMOJI[severity]} {severity.value.capitalize()} | {counts[severity]} |"
        )

    body_parts = [SUMMARY_MARKER, "## AI Code Review Summary", "", summary, "", "\n".join(table_lines)]
    if fix_pr_url:
        body_parts += ["", f"A fix PR has been opened: {fix_pr_url}"]

    try:
        pr.create_issue_comment("\n".join(body_parts))
    except Exception as exc:
        logger.error("Failed to post summary comment on PR #%s: %s", pr_number, exc)


def raise_fix_pr(
    patches: list[Patch],
    base_branch: str,
    pr_number: int,
    workspace: str,
) -> Optional[str]:
    verified = [p for p in patches if p.verified]
    if not verified:
        return None

    branch_name = f"ai-fix/pr-{pr_number}-{int(time.time())}"

    try:
        # No start-point ref: clone_workspace already leaves the workspace
        # checked out (detached) at exactly head_sha, and a plain `git clone`
        # only creates a local branch for the default branch -- head_branch
        # only exists as origin/<head_branch>, so passing it here as a
        # literal ref fails. Branching from current HEAD is also more
        # correct: it's pinned to the exact reviewed commit even if
        # head_branch has since moved.
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to create branch %s: %s", branch_name, exc.stderr)
        return None

    try:
        subprocess.run(
            ["git", "config", "user.email", FIX_COMMIT_EMAIL],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", FIX_COMMIT_NAME],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to configure git identity: %s", exc.stderr)
        return None

    applied_any = False
    for patch in verified:
        filepath = os.path.join(workspace, patch.file)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            logger.error("Failed to read %s: %s", patch.file, exc)
            continue

        if patch.original_snippet not in content:
            logger.error("Original snippet not found in %s, skipping patch", patch.file)
            continue

        new_content = content.replace(patch.original_snippet, patch.fixed_snippet, 1)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as exc:
            logger.error("Failed to write %s: %s", patch.file, exc)
            continue

        try:
            subprocess.run(
                ["git", "add", patch.file], cwd=workspace, check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "commit", "-m", patch.commit_message],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
            applied_any = True
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to commit patch for %s: %s", patch.file, exc.stderr)

    if not applied_any:
        return None

    try:
        subprocess.run(
            ["git", "push", "origin", branch_name],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to push branch %s: %s", branch_name, exc.stderr)
        return None

    try:
        repo = get_repo()
        pull = repo.create_pull(
            title=f"AI fix for PR #{pr_number}",
            body=f"Automated fixes for #{pr_number}.\n\n{FIX_PR_MARKER}",
            head=branch_name,
            base=base_branch,
        )
    except Exception as exc:
        logger.error("Failed to create fix PR for #%s: %s", pr_number, exc)
        return None

    try:
        pull.create_issue_comment(FIX_PR_APPROVAL_PROMPT)
    except Exception as exc:
        logger.error("Failed to post approval prompt on fix PR #%s: %s", pull.number, exc)

    return pull.html_url


def is_fix_pr(pr_number: int) -> bool:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        return FIX_PR_MARKER in (pr.body or "")
    except Exception as exc:
        logger.error("Failed to fetch PR #%s: %s", pr_number, exc)
        return False


def has_write_access(username: str) -> bool:
    try:
        repo = get_repo()
        return repo.get_collaborator_permission(username) in ("admin", "write")
    except Exception as exc:
        logger.error("Failed to check collaborator permission for %s: %s", username, exc)
        return False


def merge_fix_pr(pr_number: int) -> bool:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        pr.merge(
            commit_message=f"Merge AI fix PR #{pr_number}",
            merge_method=FIX_PR_MERGE_METHOD,
            delete_branch=True,
        )
        return True
    except Exception as exc:
        logger.error("Failed to merge fix PR #%s: %s", pr_number, exc)
        return False


def close_fix_pr(pr_number: int) -> bool:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        head_ref = pr.head.ref
        pr.edit(state="closed")
    except Exception as exc:
        logger.error("Failed to close fix PR #%s: %s", pr_number, exc)
        return False

    try:
        repo.get_git_ref(f"heads/{head_ref}").delete()
    except Exception as exc:
        logger.error("Failed to delete branch %s after closing PR #%s: %s", head_ref, pr_number, exc)

    return True


def post_pr_comment(pr_number: int, body: str) -> bool:
    try:
        repo = get_repo()
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)
        return True
    except Exception as exc:
        logger.error("Failed to post comment on PR #%s: %s", pr_number, exc)
        return False
