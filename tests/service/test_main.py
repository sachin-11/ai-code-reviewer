import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret-123"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from service.config import get_settings

    get_settings.cache_clear()

    from service.webhooks import router as router_module

    router_module.get_job_queue.cache_clear()

    from service.main import app

    with TestClient(app) as c:
        yield c

    router_module.get_job_queue.cache_clear()
    get_settings.cache_clear()


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _post(client, event_type: str, payload: dict, signature: str | None = None):
    body = json.dumps(payload).encode()
    sig = signature if signature is not None else _sign(body)
    return client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": event_type,
            "Content-Type": "application/json",
        },
    )


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_valid_pull_request_opened_is_queued(client):
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "head": {"sha": "abc123", "ref": "feature"},
            "base": {"sha": "def456", "ref": "main"},
        },
        "repository": {"full_name": "org/repo"},
    }
    r = _post(client, "pull_request", payload)
    assert r.status_code == 200
    assert r.json() == {"status": "queued", "job": "review_pr"}


def test_invalid_signature_rejected(client):
    payload = {"action": "opened"}
    r = _post(client, "pull_request", payload, signature="sha256=deadbeef")
    assert r.status_code == 401


def test_missing_signature_rejected(client):
    body = json.dumps({"action": "opened"}).encode()
    r = client.post("/webhook/github", content=body, headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 401


def test_unhandled_pr_action_ignored(client):
    payload = {
        "action": "closed",
        "pull_request": {
            "number": 7,
            "head": {"sha": "abc123", "ref": "feature"},
            "base": {"sha": "def456", "ref": "main"},
        },
        "repository": {"full_name": "org/repo"},
    }
    r = _post(client, "pull_request", payload)
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}


def test_review_comment_reply_queued(client):
    payload = {
        "action": "created",
        "comment": {"id": 999, "in_reply_to_id": 111, "user": {"login": "reviewer1"}},
        "pull_request": {"number": 7, "head": {"sha": "abc123"}},
        "repository": {"full_name": "org/repo"},
    }
    r = _post(client, "pull_request_review_comment", payload)
    assert r.status_code == 200
    assert r.json() == {"status": "queued", "job": "handle_conversation"}


def test_unrelated_event_type_ignored(client):
    r = _post(client, "issues", {"action": "opened"})
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}


def test_missing_server_secret_returns_500(client, monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)

    from service.config import get_settings

    get_settings.cache_clear()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 7,
            "head": {"sha": "abc123", "ref": "feature"},
            "base": {"sha": "def456", "ref": "main"},
        },
        "repository": {"full_name": "org/repo"},
    }
    r = _post(client, "pull_request", payload)
    assert r.status_code == 500
