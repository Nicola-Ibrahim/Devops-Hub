"""Catalog HTTP response models."""

from typing import Literal
from uuid import UUID

from api.core.schemas import Contract


class ResourceSizeView(Contract):
    id: str
    cpu_millis: int
    memory_bytes: int
    storage_bytes: int
    storage_enforcement: Literal["reservation_only"]


class PostgresOptionView(Contract):
    template_id: str
    version: str
    target_id: str
    size: ResourceSizeView
    max_lifetime_seconds: int
    requestable: bool
    unavailable_reason: str | None


class CatalogResponse(Contract):
    project_id: UUID
    templates: list[PostgresOptionView]
    message: str
