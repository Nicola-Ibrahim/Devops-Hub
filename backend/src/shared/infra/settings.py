"""Explicit configuration; never load a developer's .env implicitly."""

import os
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

SCHEMA_REVISION = "0005_application_delivery"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_", extra="ignore", hide_input_in_errors=True
    )

    @model_validator(mode="before")
    @classmethod
    def private_file_configuration(cls, data: object) -> object:
        values = dict(data) if isinstance(data, dict) else {}
        for name in (
            "database_url",
            "token_pepper",
            "installation_id",
            "resource_key",
            "resource_key_id",
            "metrics_token",
            "github_token",
            "github_webhook_secret",
        ):
            path = os.environ.get("PLATFORM_" + name.upper() + "_FILE")
            if path and not values.get(name):
                with Path(path).open() as source:
                    value = source.read(4097).strip()
                if not value or len(value) > 4096:
                    raise ValueError("Invalid private configuration file")
                values[name] = value
        return values

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
    installation_id: UUID | None = None

    resource_key: SecretStr | None = None
    resource_key_id: str = "local"
    docker_url: str = "unix:///var/run/docker.sock"
    postgres_image: str = "postgres:16"
    advertised_host: str = "127.0.0.1"
    local_provider_enabled: bool = False
    cookie_secure: bool = True
    browser_allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    opa_url: str = "http://127.0.0.1:8181"

    @field_validator("docker_url")
    @classmethod
    def trusted_docker_transport(cls, value: str) -> str:
        if not value.startswith("unix://"):
            raise ValueError("Only the configured local Docker socket is currently supported")
        return value

    metrics_token: SecretStr | None = None
    template_root: str | None = None
    template_workflow_repository: str | None = None
    github_organization: str | None = None
    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_webhook_secret: SecretStr | None = None
    github_allowed_repository_owner: str | None = None
    preview_owner_id: UUID | None = None
    preview_ttl_seconds: int = Field(default=14400, ge=60, le=604800)
    approved_local_images: tuple[str, ...] = ()
