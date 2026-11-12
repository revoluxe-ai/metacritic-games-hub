import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./metacritic.db"
    metacritic_api_key: str = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
    metacritic_base: str = "https://backend.metacritic.com"
    metacritic_site: str = "https://www.metacritic.com"

    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str | None = None
    llm_model: str = "gemini-3.1-flash-lite"
    llm_max_retries: int = 3
    llm_retry_backoff_seconds: float = 2.0
    llm_request_delay_seconds: float = 0.75
    llm_max_review_snippets: int = 8
    llm_max_output_tokens: int = 280
    llm_max_transcript_chars: int = 2000

    games_per_run: int = 20
    scheduler_interval_minutes: int = 60
    scraper_enabled: bool = True
    youtube_enabled: bool = True
    run_scheduler: bool = False
    run_ingestion_on_startup: bool = False

    app_host: str = "0.0.0.0"
    app_port: int = int(os.environ.get("PORT", os.environ.get("APP_PORT", "8742")))
    secret_key: str = "dev-secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()
