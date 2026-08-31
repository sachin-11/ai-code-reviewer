import base64
import json
from unittest.mock import MagicMock, patch

from github import GithubException

from agent import memory_store
from agent.github_client import _format_issue_comment
from agent.schemas import Issue


def _make_issue(**overrides):
    defaults = dict(
        file="a.py",
        line_start=1,
        line_end=2,
        severity="critical",
        category="security",
        title="SQL injection",
        description="d",
        suggestion="s",
        confidence=0.9,
        fixable=True,
    )
    defaults.update(overrides)
    return Issue(**defaults)


def test_marker_round_trips_through_posted_comment():
    issue = _make_issue()
    body = _format_issue_comment(issue)
    parsed = memory_store.parse_marker(body)

    assert parsed is not None
    assert parsed["file"] == "a.py"
    assert parsed["category"] == "security"
    assert parsed["title"] == "SQL injection"


def test_parse_marker_returns_none_for_plain_text():
    assert memory_store.parse_marker("just a human comment") is None


def test_scan_for_new_dismissals_records_thumbs_down_with_reactor():
    issue1 = _make_issue()
    issue2 = _make_issue(file="b.py", category="style", title="unused import", severity="low")

    def make_comment(body, reactions):
        c = MagicMock()
        c.body = body
        c.get_reactions.return_value = reactions
        return c

    def make_reaction(content, login):
        r = MagicMock()
        r.content = content
        r.user = MagicMock(login=login)
        return r

    comment1 = make_comment(_format_issue_comment(issue1), [make_reaction("-1", "alice")])
    comment2 = make_comment(_format_issue_comment(issue2), [make_reaction("+1", "bob")])
    comment3 = make_comment("looks good", [])

    pr = MagicMock()
    pr.get_review_comments.return_value = [comment1, comment2, comment3]

    memory = memory_store._empty_memory()
    new_count = memory_store.scan_for_new_dismissals(pr, memory)

    assert new_count == 1
    assert len(memory["dismissed_fingerprints"]) == 1
    dismissal = list(memory["dismissed_fingerprints"].values())[0]
    assert dismissal["dismissed_by"] == "alice"
    assert memory["author_notes"]["alice"]["dismiss_counts"] == {"security": 1}
    assert "bob" not in memory["author_notes"]


def test_scan_for_new_dismissals_is_idempotent():
    issue = _make_issue()
    comment = MagicMock()
    comment.body = _format_issue_comment(issue)
    comment.get_reactions.return_value = [MagicMock(content="-1", user=MagicMock(login="alice"))]

    pr = MagicMock()
    pr.get_review_comments.return_value = [comment]

    memory = memory_store._empty_memory()
    memory_store.scan_for_new_dismissals(pr, memory)
    second_pass_count = memory_store.scan_for_new_dismissals(pr, memory)

    assert second_pass_count == 0
    assert memory["author_notes"]["alice"]["dismiss_counts"]["security"] == 1


def test_load_memory_returns_empty_on_404():
    with patch("agent.memory_store.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(404, {"message": "Not Found"}, None)
        mock_get_repo.return_value = mock_repo

        assert memory_store.load_memory() == {"dismissed_fingerprints": {}, "author_notes": {}}


def test_load_memory_decodes_existing_content():
    stored = {"dismissed_fingerprints": {"abc": {"file": "a.py"}}, "author_notes": {}}

    with patch("agent.memory_store.github_client.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        content_file = MagicMock()
        content_file.content = base64.b64encode(json.dumps(stored).encode()).decode()
        mock_repo.get_contents.return_value = content_file
        mock_get_repo.return_value = mock_repo

        assert memory_store.load_memory() == stored
