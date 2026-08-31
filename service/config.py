import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        self.redis_url = os.environ.get("REDIS_URL", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
