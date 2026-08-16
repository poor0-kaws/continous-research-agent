from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./research.db"
    groq_api_key: str = ""
    groq_daily_request_limit: int = 100
    groq_daily_token_limit: int = 150_000
    compound_daily_search_limit: int = 25
    openalex_api_key: str = ""
    source_contact_email: str = ""
    app_timezone: str = "America/New_York"
    source_catalog_path: Path = Field(default=PROJECT_ROOT / "config" / "source_catalog.yaml")
    max_source_bytes: int = 2_000_000
    worker_poll_seconds: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
