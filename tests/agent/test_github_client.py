import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from agent.github_client import FIX_COMMIT_EMAIL, FIX_COMMIT_NAME, raise_fix_pr
from agent.schemas import Issue, Patch


def test_raise_fix_pr_configures_git_identity_before_committing(tmp_path):
    base = tmp_path
    bare = base / "remote.git"
    ws = base / "ws"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(bare), str(ws)], check=True, capture_output=True)

    subprocess.run(["git", "config", "user.email", "seed@example.com"], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.name", "seed"], cwd=ws, check=True)

    a_path = ws / "a.py"
    a_path.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ws, check=True, capture_output=True)

    # Simulate a fresh CI checkout with no configured identity.
    subprocess.run(["git", "config", "--unset", "user.email"], cwd=ws, check=True)
    subprocess.run(["git", "config", "--unset", "user.name"], cwd=ws, check=True)

    issue = Issue(
        file="a.py",
        line_start=1,
        line_end=2,
        severity="high",
        category="bug",
        title="t",
        description="d",
        suggestion="s",
        confidence=0.9,
        fixable=True,
    )
    patch = Patch(
        issue=issue,
        file="a.py",
        original_snippet="return a + b",
        fixed_snippet="return a + b  # fixed",
        commit_message="fix: patch",
        verified=True,
    )

    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.create_pull.return_value = MagicMock(html_url="https://github.com/x/y/pull/1")
        mock_get_repo.return_value = mock_repo

        result = raise_fix_pr([patch], "main", "main", 7, str(ws))

    assert result == "https://github.com/x/y/pull/1"

    log = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"], cwd=ws, capture_output=True, text=True
    )
    assert log.stdout.strip() == f"{FIX_COMMIT_NAME} <{FIX_COMMIT_EMAIL}>"

    branches = subprocess.run(["git", "branch", "-a"], cwd=bare, capture_output=True, text=True)
    assert "ai-fix/pr-7-" in branches.stdout
