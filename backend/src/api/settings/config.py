"""Validated API settings and HTTP-only browser cookie policy."""

from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """HTTP metadata and OpenAPI endpoints, loaded from ``API_*`` environment values.

    Dotenv loading is intentionally disabled: runtime configuration comes from the
    process environment or an explicitly injected settings instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
        frozen=True,
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


@lru_cache(maxsize=1)
def get_api_settings() -> APISettings:
    """Load API settings once per process; tests can clear this cache explicitly."""
    return APISettings()


@dataclass(frozen=True, slots=True)
class BrowserCookiePolicy:
    secure: bool
