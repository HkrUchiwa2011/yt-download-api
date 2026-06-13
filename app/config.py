import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_KEY: str = os.getenv("API_KEY", "changeme")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    TMP_DIR: str = "/tmp/yt-downloads"
    FILE_TTL_MINUTES: int = 30
    MAX_DURATION_SECONDS: int = 3600
    MAX_FILESIZE_MB: int = 500
    PROXY_URL: str | None = os.getenv("PROXY_URL", None)

    RATE_LIMIT_PER_MINUTE_IP: int = 10
    RATE_LIMIT_PER_MINUTE_KEY: int = 30
    MAX_CONCURRENT_DOWNLOADS: int = 5

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
