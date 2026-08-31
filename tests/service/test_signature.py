import hashlib
import hmac

from service.webhooks.signature import verify_signature


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    body = b'{"hello": "world"}'
    secret = "test-secret"
    assert verify_signature(body, _sign(body, secret), secret) is True


def test_wrong_secret_rejected():
    body = b'{"hello": "world"}'
    assert verify_signature(body, _sign(body, "wrong-secret"), "test-secret") is False


def test_tampered_body_rejected():
    secret = "test-secret"
    sig = _sign(b'{"hello": "world"}', secret)
    assert verify_signature(b'{"hello": "tampered"}', sig, secret) is False


def test_missing_prefix_rejected():
    assert verify_signature(b"body", "deadbeef", "secret") is False


def test_empty_secret_always_rejects():
    body = b"body"
    sig = _sign(body, "")
    assert verify_signature(body, sig, "") is False
