from service.webhooks.events import parse_pull_request_event, parse_review_comment_event


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
