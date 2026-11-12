from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./metacritic.db"
    metacritic_api_key: str = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
    metacritic_base: str = "https://backend.metacritic.com"
    metacritic_site: str = "https://www.metacritic.com"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    games_per_run: int = 20
    scheduler_interval_minutes: int = 60
    scraper_enabled: bool = True

    app_host: str = "0.0.0.0"
    app_port: int = 8742
    secret_key: str = "dev-secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()
