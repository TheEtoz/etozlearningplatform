"""Application configuration loaded from environment variables.

Keeping configuration in one place prevents database URLs, secret keys, and
deployment-specific values from being scattered throughout the codebase.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings.

    Pydantic reads values from the process environment first and then from a
    local ``.env`` file. Production services can therefore inject secrets
    without storing them in source control.
    """

    app_name: str = "ETOZ Learning Platform"
    debug: bool = False
    secret_key: str = Field(
        default="change-this-to-a-long-random-string",
        min_length=16,
    )
    access_token_expire_minutes: int = Field(default=30, ge=1)
    database_url: str = (
        "postgresql+psycopg2://user:password@127.0.0.1:5432/etoz_db"
    )
    cors_origins: list[str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8502",
        "http://127.0.0.1:8502",
        "http://localhost:8503",
        "http://127.0.0.1:8503",
    ]

    # Docker sandbox settings for Step 7 coding execution.
    docker_image: str = "etoz-python-runner"
    docker_memory_limit: str = "128m"
    docker_cpu_limit: float = Field(default=0.5, gt=0, le=4)
    docker_timeout_seconds: int = Field(default=10, ge=1, le=120)

    # Usernames that become admins on register (comma-separated in .env).
    admin_usernames: list[str] = Field(default_factory=list)

    # Simple in-process rate limits (requests per minute per client IP).
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10_000)
    auth_rate_limit_per_minute: int = Field(default=20, ge=5, le=1_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the application process."""

    return Settings()


settings = get_settings()
