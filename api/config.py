from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PHANTOMCARE_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./phantomcare.db"
    cache_dir: str = "./cache"
    analysis_dir: str = "./data/analysis"
    dashboard_origin: str = "http://localhost:3000"
    agent_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

