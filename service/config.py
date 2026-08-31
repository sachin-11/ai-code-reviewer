import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
