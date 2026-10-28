from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All fields can be set via env (upper-case)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "dev"
    secret_key: str = "dev-only-change-me-0123456789abcdef"
    invite_codes: str = "W1-DEMO"
    data_dir: Path = Path("./data")
    database_url: str | None = None
    max_upload_mb: int = 20
    token_ttl_days: int = 30
    cors_origins: str = "*"

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 2

    @property
    def invite_code_set(self) -> set[str]:
        return {code.strip() for code in self.invite_codes.split(",") if code.strip()}

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "users").mkdir(parents=True, exist_ok=True)
        if self.env == "prod" and self.secret_key == "dev-only-change-me-0123456789abcdef":
            raise RuntimeError("Set SECRET_KEY before running with ENV=prod")
        if self.env == "prod" and len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters")


@lru_cache
def get_settings() -> Settings:
    return Settings()
