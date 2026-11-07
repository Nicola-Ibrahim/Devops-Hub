"""Validated immutable values used by platform entities and aggregates."""

from developer_platform.domain.value_objects.idempotency_key import IdempotencyKey
from developer_platform.domain.value_objects.image_digest import ImageDigest
from developer_platform.domain.value_objects.lease import ResourceLease
from developer_platform.domain.value_objects.repository_slug import RepositorySlug
from developer_platform.domain.value_objects.resource_endpoint import ResourceEndpoint
from developer_platform.domain.value_objects.resource_name import ResourceName
from developer_platform.domain.value_objects.resource_spec import ResourceSpec
from developer_platform.domain.value_objects.revision import ResourceRevision
from developer_platform.domain.value_objects.statuses import (
    DeletionReason,
    DesiredState,
    ResourceStatus,
)

__all__ = [
    "DeletionReason",
    "DesiredState",
    "IdempotencyKey",
    "ImageDigest",
    "RepositorySlug",
    "ResourceEndpoint",
    "ResourceLease",
    "ResourceName",
    "ResourceRevision",
    "ResourceSpec",
    "ResourceStatus",
]
