"""Explicit configuration; never load a developer's .env implicitly."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

SCHEMA_REVISION = "0001_foundation"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    database_connect_timeout: int = Field(default=3, ge=1, le=30)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("A valid PostgreSQL connection URL is required") from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError("Use the postgresql+psycopg driver")
        return value


class Settings(DatabaseSettings):
    environment: Literal["local", "test", "server"] = "local"
    token_pepper: SecretStr = Field(min_length=32)
