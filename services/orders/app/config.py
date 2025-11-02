"""Configuration utilities for Orders service."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = Field(default="postgresql+psycopg://orders:orders@localhost:5432/orders")
    event_broker_url: str = Field(default="kafka://localhost:9092")
    service_name: str = Field(default="orders-service")
    feature_flag_task_intent: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="ORDERS_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
