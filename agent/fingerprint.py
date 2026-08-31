import hashlib


def fingerprint(file: str, category: str, title: str) -> str:
    key = f"{file}|{category}|{title.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
