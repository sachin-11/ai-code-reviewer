import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from agent.github_client import (
    FIX_COMMIT_EMAIL,
    FIX_COMMIT_NAME,
    FIX_PR_MARKER,
    close_fix_pr,
    has_write_access,
    is_fix_pr,
    merge_fix_pr,
    raise_fix_pr,
)
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

        result = raise_fix_pr([patch], "main", 7, str(ws))

    assert result == "https://github.com/x/y/pull/1"

    log = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"], cwd=ws, capture_output=True, text=True
    )
    assert log.stdout.strip() == f"{FIX_COMMIT_NAME} <{FIX_COMMIT_EMAIL}>"

    branches = subprocess.run(["git", "branch", "-a"], cwd=bare, capture_output=True, text=True)
    assert "ai-fix/pr-7-" in branches.stdout

    body = mock_repo.create_pull.call_args.kwargs["body"]
    assert FIX_PR_MARKER in body
    assert "draft" not in mock_repo.create_pull.call_args.kwargs


def test_is_fix_pr_true_when_marker_present():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = MagicMock(body=f"Automated fixes.\n\n{FIX_PR_MARKER}")
        mock_get_repo.return_value = mock_repo
        assert is_fix_pr(9) is True


def test_is_fix_pr_false_for_a_regular_pr():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = MagicMock(body="just a normal PR description")
        mock_get_repo.return_value = mock_repo
        assert is_fix_pr(9) is False


def test_has_write_access_true_for_write_permission():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.get_collaborator_permission.return_value = "write"
        mock_get_repo.return_value = mock_repo
        assert has_write_access("owner1") is True


def test_has_write_access_false_for_read_permission():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.get_collaborator_permission.return_value = "read"
        mock_get_repo.return_value = mock_repo
        assert has_write_access("random_user") is False


def test_merge_fix_pr_calls_merge_with_delete_branch():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_get_repo.return_value = mock_repo

        assert merge_fix_pr(9) is True

    assert mock_pr.merge.call_args.kwargs["delete_branch"] is True


def test_close_fix_pr_closes_and_deletes_branch():
    with mock_patch("agent.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_pr = MagicMock(head=MagicMock(ref="ai-fix/pr-9-123"))
        mock_repo.get_pull.return_value = mock_pr
        mock_get_repo.return_value = mock_repo

        assert close_fix_pr(9) is True

    mock_pr.edit.assert_called_once_with(state="closed")
    mock_repo.get_git_ref.assert_called_once_with("heads/ai-fix/pr-9-123")
