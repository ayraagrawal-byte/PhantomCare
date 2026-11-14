from functools import lru_cache

from pydantic import Field
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
    agent_live_enabled: bool = False
    agent_max_tool_calls: int = Field(default=8, ge=8, le=12)
    agent_max_tokens: int = Field(default=1200, ge=256, le=4000)
    agent_timeout_seconds: int = Field(default=25, ge=5, le=60)
    agent_max_retries: int = Field(default=0, ge=0, le=1)
    agent_requests_per_window: int = Field(default=5, ge=1, le=20)
    agent_rate_window_seconds: int = Field(default=60, ge=10, le=3600)
    agent_max_concurrent: int = Field(default=2, ge=1, le=4)
    agent_client_hash_secret: str | None = None
    agent_redis_url: str | None = None
    agent_redis_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

