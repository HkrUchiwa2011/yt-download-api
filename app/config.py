from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    API_KEY: SecretStr
    REDIS_NAMESPACE: str = Field(default="yt", pattern=r"^[a-z0-9_-]{1,40}$")
    REDIS_URL: SecretStr = SecretStr("redis://localhost:6379/0")
    TMP_DIR: Path = Path("/tmp/yt-downloads")  # noqa: S108 - dedicated directory, owner-only permissions
    FILE_TTL_MINUTES: int = Field(default=30, ge=1, le=1440)
    MAX_DURATION_SECONDS: int = Field(default=3600, ge=1, le=86400)
    MAX_FILESIZE_MB: int = Field(default=500, ge=1, le=10000)
    MIN_FREE_SPACE_MB: int = Field(default=256, ge=0)
    JOB_TIMEOUT_SECONDS: int = Field(default=900, ge=10, le=86400)
    SOCKET_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=120)
    PROXY_URL: SecretStr | None = None
    RATE_LIMIT_PER_MINUTE_IP: int = Field(default=10, ge=1)
    RATE_LIMIT_PER_MINUTE_KEY: int = Field(default=30, ge=1)
    STATUS_RATE_LIMIT_PER_MINUTE_IP: int = Field(default=120, ge=1)
    STATUS_RATE_LIMIT_PER_MINUTE_KEY: int = Field(default=300, ge=1)
    MAX_CONCURRENT_INFO_REQUESTS: int = Field(default=2, ge=1, le=8)
    MAX_CONCURRENT_DOWNLOADS: int = Field(default=5, ge=1, le=32)
    EMBEDDED_WORKERS: int = Field(default=1, ge=0, le=32)
    WEBHOOK_ALLOWED_HOSTS: list[str] = Field(default_factory=list)
    WEBHOOK_SECRET: SecretStr | None = None
    ENABLE_DOCS: bool = False

    @field_validator("API_KEY")
    @classmethod
    def strong_api_key(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if (
            not secret.isascii()
            or any(char.isspace() for char in secret)
            or not 32 <= len(secret) <= 512
            or secret.lower()
            in {
                "change-this-to-a-strong-secret",
                "replace-with-a-random-secret-of-at-least-32-characters",
            }
        ):
            raise ValueError("API_KEY must be a random secret of at least 32 characters")
        return value

    @field_validator("PROXY_URL", "WEBHOOK_SECRET", mode="before")
    @classmethod
    def empty_secret(cls, value):
        return value or None

    @field_validator("TMP_DIR")
    @classmethod
    def absolute_directory(cls, value: Path) -> Path:
        if not value.is_absolute() or value == Path("/"):
            raise ValueError("TMP_DIR must be an absolute dedicated directory")
        return value

    @field_validator("WEBHOOK_ALLOWED_HOSTS")
    @classmethod
    def normalize_hosts(cls, values: list[str]) -> list[str]:
        from app.security import normalize_hostname

        return [normalize_hostname(value) for value in values]

    @model_validator(mode="after")
    def webhook_signing(self):
        if self.WEBHOOK_ALLOWED_HOSTS and (
            not self.WEBHOOK_SECRET or len(self.WEBHOOK_SECRET.get_secret_value()) < 32
        ):
            raise ValueError("WEBHOOK_SECRET of at least 32 characters is required for webhooks")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
