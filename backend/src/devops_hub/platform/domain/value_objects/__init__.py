"""Validated immutable values used by platform entities and aggregates."""

from devops_hub.platform.domain.value_objects.idempotency_key import IdempotencyKey
from devops_hub.platform.domain.value_objects.image_digest import ImageDigest
from devops_hub.platform.domain.value_objects.lease import ResourceLease
from devops_hub.platform.domain.value_objects.repository_slug import RepositorySlug
from devops_hub.platform.domain.value_objects.resource_endpoint import ResourceEndpoint
from devops_hub.platform.domain.value_objects.resource_name import ResourceName
from devops_hub.platform.domain.value_objects.resource_spec import ResourceSpec
from devops_hub.platform.domain.value_objects.revision import ResourceRevision
from devops_hub.platform.domain.value_objects.statuses import (
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
