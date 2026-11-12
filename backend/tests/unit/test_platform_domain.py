from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from devops_hub.platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from devops_hub.platform.domain.errors import DomainError
from devops_hub.platform.domain.services.resource_admission import (
    CapacitySnapshot,
    ResourceAdmissionPolicy,
)
from devops_hub.platform.domain.value_objects.resource_name import ResourceName
from devops_hub.platform.domain.value_objects.resource_spec import ResourceSpec
from devops_hub.platform.domain.value_objects.revision import ResourceRevision
from devops_hub.platform.domain.value_objects.statuses import DesiredState, ResourceStatus


def _resource(now: datetime) -> ResourceLifecycle:
    return ResourceLifecycle.request(
        resource_id=uuid4(),
        project_id=uuid4(),
        environment_id=uuid4(),
        owner_id=uuid4(),
        installation_id=uuid4(),
        name=ResourceName(" feature-db "),
        specification=ResourceSpec("postgres", "16", "local", "small"),
        now=now,
        ttl_seconds=1800,
        max_lifetime_seconds=7200,
    )


def test_resource_request_normalizes_name_and_owns_initial_lifecycle() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    lifecycle = _resource(now)

    assert lifecycle.resource.name.value == "feature-db"
    assert lifecycle.resource.status is ResourceStatus.PENDING
    assert lifecycle.resource.desired_state is DesiredState.RUNNING
    assert lifecycle.resource.lease.expires_at == now + timedelta(minutes=30)


def test_resource_renewal_is_revision_fenced_and_deletion_is_idempotent() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lifecycle = _resource(now)

    with pytest.raises(DomainError, match="revision"):
        lifecycle.renew(
            expected_revision=ResourceRevision(2),
            requested_expiry=now + timedelta(hours=1),
            now=now,
        )

    deleting = lifecycle.request_deletion()
    assert deleting.resource.status is ResourceStatus.DELETING
    assert deleting.request_deletion() == deleting


def test_resource_admission_rejects_capacity_overrun() -> None:
    with pytest.raises(DomainError, match="quota"):
        ResourceAdmissionPolicy.require_capacity(
            CapacitySnapshot(2, 500, 1024, 2048),
            CapacitySnapshot(2, 1000, 2048, 4096),
            CapacitySnapshot(1, 100, 256, 512),
        )
