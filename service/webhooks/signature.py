import hashlib
import hmac


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
