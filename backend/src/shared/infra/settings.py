"""Explicit configuration; never load a developer's .env implicitly."""

import json
import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

SCHEMA_REVISION = "0001_initial_schema"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_",
        env_file=None,
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
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
            if name == "database_url":
                path = path or os.environ.get("DATABASE_URL_FILE")
            if path and not values.get(name):
                with Path(path).open() as source:
                    value = source.read(4097).strip()
                if not value or len(value) > 4096:
                    raise ValueError("Invalid private configuration file")
                values[name] = value
        return values

    database_url: SecretStr = Field(
        validation_alias=AliasChoices("PLATFORM_DATABASE_URL", "DATABASE_URL")
    )
    database_connect_timeout: int = Field(default=3, ge=1, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=-1, le=86400)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("A valid PostgreSQL connection URL is required") from None
        if url.drivername == "postgresql":
            return SecretStr(
                url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
            )
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
    browser_allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    opa_url: str = "http://127.0.0.1:8181"

    @field_validator("docker_url")
    @classmethod
    def trusted_docker_transport(cls, value: str) -> str:
        if not value.startswith("unix://"):
            raise ValueError("Only the configured local Docker socket is currently supported")
        return value

    @field_validator("browser_allowed_origins", mode="before")
    @classmethod
    def parse_browser_allowed_origins(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            value = _parse_string_list(value)
        if not isinstance(value, (list, tuple)):
            raise ValueError("Browser origins must be a comma-separated list or JSON array")
        origins = tuple(item.strip().rstrip("/") for item in value if isinstance(item, str))
        if len(origins) != len(value) or any(not _is_http_origin(item) for item in origins):
            raise ValueError("Browser origins must be absolute HTTP(S) origins without paths")
        return origins

    metrics_token: SecretStr | None = None
    template_root: str | None = None
    github_organization: str | None = None
    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_webhook_secret: SecretStr | None = None
    github_allowed_repository_owner: str | None = None
    preview_owner_id: UUID | None = None
    preview_ttl_seconds: int = Field(default=14400, ge=60, le=604800)
    approved_local_images: Annotated[tuple[str, ...], NoDecode] = ()

    @field_validator("approved_local_images", mode="before")
    @classmethod
    def parse_approved_local_images(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            value = _parse_string_list(value)
        if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
            raise ValueError("Approved images must be a comma-separated list or JSON array")
        return tuple(item.strip() for item in value if item.strip())


def _parse_string_list(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array")
        return parsed
    return [item.strip() for item in stripped.split(",") if item.strip()]


def _is_http_origin(value: str) -> bool:
    from urllib.parse import urlsplit

    try:
        url = urlsplit(value)
        return (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and not url.path
            and not url.query
            and not url.fragment
            and "*" not in url.netloc
        )
    except ValueError:
        return False
