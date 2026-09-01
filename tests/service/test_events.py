from service.webhooks.events import (
    parse_fix_pr_comment_event,
    parse_pull_request_event,
    parse_review_comment_event,
)


def test_pull_request_opened_parsed():
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "head": {"sha": "headsha123", "ref": "feature-x"},
            "base": {"sha": "basesha456", "ref": "main"},
        },
        "repository": {"full_name": "org/repo"},
    }
    assert parse_pull_request_event(payload) == {
        "pr_number": 42,
        "head_sha": "headsha123",
        "base_sha": "basesha456",
        "head_branch": "feature-x",
        "base_branch": "main",
        "repo_full_name": "org/repo",
    }


def test_pull_request_unhandled_action_ignored():
    payload = {
        "action": "closed",
        "pull_request": {"number": 1, "head": {"sha": "a", "ref": "b"}, "base": {"sha": "c", "ref": "d"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_pull_request_event(payload) is None


def test_review_comment_reply_parsed():
    payload = {
        "action": "created",
        "comment": {"id": 555, "in_reply_to_id": 100, "user": {"login": "reviewer1"}},
        "pull_request": {"number": 42, "head": {"sha": "headsha"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_review_comment_event(payload) == {
        "pr_number": 42,
        "comment_id": 555,
        "comment_author": "reviewer1",
        "repo_full_name": "org/repo",
        "head_sha": "headsha",
    }


def test_review_comment_top_level_not_a_reply_ignored():
    payload = {
        "action": "created",
        "comment": {"id": 556, "in_reply_to_id": None, "user": {"login": "reviewer1"}},
        "pull_request": {"number": 42, "head": {"sha": "headsha"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_review_comment_event(payload) is None


def test_fix_pr_approve_comment_parsed():
    payload = {
        "action": "created",
        "issue": {"number": 9, "pull_request": {"url": "https://api.github.com/.../pulls/9"}},
        "comment": {"body": "  Approve  ", "user": {"login": "owner1"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_fix_pr_comment_event(payload) == {
        "pr_number": 9,
        "decision": "approve",
        "comment_author": "owner1",
        "repo_full_name": "org/repo",
    }


def test_fix_pr_reject_comment_parsed():
    payload = {
        "action": "created",
        "issue": {"number": 9, "pull_request": {}},
        "comment": {"body": "reject", "user": {"login": "owner1"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_fix_pr_comment_event(payload)["decision"] == "reject"


def test_issue_comment_on_plain_issue_ignored():
    payload = {
        "action": "created",
        "issue": {"number": 9},
        "comment": {"body": "approve", "user": {"login": "owner1"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_fix_pr_comment_event(payload) is None


def test_issue_comment_unrelated_text_ignored():
    payload = {
        "action": "created",
        "issue": {"number": 9, "pull_request": {}},
        "comment": {"body": "nice work!", "user": {"login": "owner1"}},
        "repository": {"full_name": "org/repo"},
    }
    assert parse_fix_pr_comment_event(payload) is None
