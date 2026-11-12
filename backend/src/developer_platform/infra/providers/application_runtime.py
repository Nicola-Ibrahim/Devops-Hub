"""Naming helpers shared with the local database provider."""

from uuid import UUID


def managed_resource_container_name(installation_id: UUID, resource_id: UUID) -> str:
    return f"dh-{installation_id.hex[:8]}-{resource_id.hex}"
