import logging
import os
import subprocess
import time
from typing import Optional

from github import Auth, Github
from github.Repository import Repository

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

MIN_COMMENT_CONFIDENCE = 0.6
POST_DELAY_SECONDS = 0.5

FIX_COMMIT_NAME = "ai-code-reviewer[bot]"
FIX_COMMIT_EMAIL = "ai-code-reviewer[bot]@users.noreply.github.com"


def get_client() -> Github:
    token = os.environ["GITHUB_TOKEN"]
    return Github(auth=Auth.Token(token))


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
    return (
        f"{emoji} **{issue.severity.value.upper()} · {issue.category.value}**\n\n"
        f"**{issue.title}**\n\n"
        f"{issue.description}\n\n"
        f"**Suggestion:** {issue.suggestion}"
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
    head_branch: str,
    base_branch: str,
    pr_number: int,
    workspace: str,
) -> Optional[str]:
    verified = [p for p in patches if p.verified]
    if not verified:
        return None

    branch_name = f"ai-fix/pr-{pr_number}-{int(time.time())}"

    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name, head_branch],
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
            body=f"Automated fixes for #{pr_number}.",
            head=branch_name,
            base=base_branch,
            draft=True,
        )
        return pull.html_url
    except Exception as exc:
        logger.error("Failed to create fix PR for #%s: %s", pr_number, exc)
        return None
