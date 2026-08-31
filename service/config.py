import os
from functools import lru_cache


DEFAULT_DATABASE_URL = "postgresql://ai_reviewer:ai_reviewer@localhost:5442/ai_reviewer"


class Settings:
    def __init__(self) -> None:
        self.github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        self.redis_url = os.environ.get("REDIS_URL", "")
        self.database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@lru_cache
def get_settings() -> Settings:
    return Settings()
