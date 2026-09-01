import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from agent import github_client
from agent.github_client import (
    FIX_COMMIT_EMAIL,
    FIX_COMMIT_NAME,
    FIX_PR_MARKER,
    close_fix_pr,
    get_git_auth_token,
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


def test_using_github_app_false_without_both_vars(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    assert github_client._using_github_app() is False

    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    assert github_client._using_github_app() is False


def test_using_github_app_true_when_both_set(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "fake-key")
    assert github_client._using_github_app() is True


def test_get_authenticated_login_uses_app_slug_when_app_configured(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "fake-key")
    monkeypatch.setenv("GITHUB_APP_SLUG", "my-bot")
    assert github_client.get_authenticated_login() == "my-bot[bot]"


def test_get_git_auth_token_uses_installation_token_when_app_configured(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "fake-key")

    with mock_patch(
        "agent.github_client._get_installation_token", return_value="inst-token-xyz"
    ) as mock_get:
        token = get_git_auth_token("org/repo")

    assert token == "inst-token-xyz"
    mock_get.assert_called_once_with("org/repo")


def test_get_git_auth_token_falls_back_to_pat_without_app(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "pat-value")
    assert get_git_auth_token("org/repo") == "pat-value"


def test_installation_token_cache_reuses_unexpired_token():
    github_client._installation_token_cache.clear()
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    github_client._installation_token_cache["org/repo"] = ("cached-token", future)

    with mock_patch("agent.github_client._get_integration") as mock_get_integration:
        token = github_client._get_installation_token("org/repo")

    assert token == "cached-token"
    assert not mock_get_integration.called
    github_client._installation_token_cache.clear()


def test_installation_token_cache_refetches_when_expired():
    github_client._installation_token_cache.clear()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    github_client._installation_token_cache["org/repo"] = ("stale-token", past)

    mock_installation = MagicMock(id=999)
    mock_auth = MagicMock(token="fresh-token", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    mock_integration = MagicMock()
    mock_integration.get_repo_installation.return_value = mock_installation
    mock_integration.get_access_token.return_value = mock_auth

    with mock_patch("agent.github_client._get_integration", return_value=mock_integration):
        token = github_client._get_installation_token("org/repo")

    assert token == "fresh-token"
    mock_integration.get_repo_installation.assert_called_once_with("org", "repo")
    mock_integration.get_access_token.assert_called_once_with(999)
    github_client._installation_token_cache.clear()
