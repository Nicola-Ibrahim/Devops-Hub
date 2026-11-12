"""Validated API settings and HTTP-only browser cookie policy."""

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class APISettings(BaseSettings):
    """HTTP metadata and OpenAPI endpoints, loaded from ``API_*`` environment values.

    Dotenv loading is intentionally disabled: runtime configuration comes from the
    process environment or an explicitly injected settings instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=None,
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
        frozen=True,
        populate_by_name=True,
    )

    title: str = Field(default="DevOps Hub API", min_length=1, max_length=120)
    version: str = Field(default="0.1.0", min_length=1, max_length=32)
    description: str = Field(
        default=(
            "Developer platform API for identity, projects, approved resources, "
            "application templates, and durable delivery workflows."
        ),
        max_length=2000,
    )
    openapi_url: str | None = "/openapi.json"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ()
    trusted_hosts: Annotated[tuple[str, ...], NoDecode] = ()

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: object) -> tuple[str, ...]:
        origins = _parse_values(value)
        normalized = tuple(origin.rstrip("/") for origin in origins)
        if any(not _is_http_origin(origin) for origin in normalized):
            raise ValueError("CORS origins must be absolute HTTP(S) origins without paths")
        return normalized

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: object) -> tuple[str, ...]:
        hosts = _parse_values(value)
        if any(not host or "/" in host or " " in host for host in hosts):
            raise ValueError("Trusted hosts must be host names or supported wildcard patterns")
        return hosts


def _parse_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith("["):
            value = json.loads(stripped)
        else:
            value = stripped.split(",")
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError("Expected a comma-separated string or JSON array")
    return tuple(item.strip() for item in value if item.strip())


def _is_http_origin(value: str) -> bool:
    try:
        origin = urlsplit(value)
        return (
            origin.scheme in {"http", "https"}
            and bool(origin.hostname)
            and origin.username is None
            and origin.password is None
            and not origin.path
            and not origin.query
            and not origin.fragment
            and "*" not in origin.netloc
        )
    except ValueError:
        return False


@lru_cache(maxsize=1)
def get_api_settings() -> APISettings:
    """Load API settings once per process; tests can clear this cache explicitly."""
    return APISettings()


@dataclass(frozen=True, slots=True)
class BrowserCookiePolicy:
    secure: bool
