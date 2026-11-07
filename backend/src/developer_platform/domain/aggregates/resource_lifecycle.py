"""Aggregate root for a temporary resource and its lease/state transitions."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from developer_platform.domain.entities.resource import TemporaryResource
from developer_platform.domain.errors import DomainError
from developer_platform.domain.leases import LeasePolicy
from developer_platform.domain.resources import transition_status
from developer_platform.domain.value_objects.lease import ResourceLease
from developer_platform.domain.value_objects.resource_name import ResourceName
from developer_platform.domain.value_objects.resource_spec import ResourceSpec
from developer_platform.domain.value_objects.revision import ResourceRevision
from developer_platform.domain.value_objects.statuses import DesiredState, ResourceStatus


@dataclass(frozen=True, slots=True)
class ResourceLifecycle:
    resource: TemporaryResource

    @classmethod
    def request(
        cls,
        *,
        resource_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        owner_id: UUID,
        installation_id: UUID,
        name: ResourceName,
        specification: ResourceSpec,
        now: datetime,
        ttl_seconds: int,
        max_lifetime_seconds: int,
    ) -> "ResourceLifecycle":
        expiry = LeasePolicy(max_lifetime_seconds).initial_expiry(now, ttl_seconds)
        return cls(
            TemporaryResource(
                id=resource_id,
                project_id=project_id,
                environment_id=environment_id,
                owner_id=owner_id,
                installation_id=installation_id,
                name=name,
                specification=specification,
                lease=ResourceLease(now, expiry, max_lifetime_seconds),
                desired_state=DesiredState.RUNNING,
                status=ResourceStatus.PENDING,
                revision=1,
                generation=1,
                created_at=now,
            )
        )

    def renew(
        self, *, expected_revision: ResourceRevision, requested_expiry: datetime, now: datetime
    ) -> "ResourceLifecycle":
        current = self.resource
        if current.revision != expected_revision.value:
            raise DomainError("Resource revision changed.")
        expiry = LeasePolicy(current.lease.max_lifetime_seconds).renewal_expiry(
            created_at=current.created_at,
            current_expiry=current.lease.expires_at,
            requested_expiry=requested_expiry,
            now=now,
            desired_state=current.desired_state,
            status=current.status,
        )
        return ResourceLifecycle(
            replace(
                current,
                lease=replace(current.lease, expires_at=expiry),
                revision=current.revision + 1,
            )
        )

    def accepted_at(self, accepted_at: datetime) -> "ResourceLifecycle":
        """Rebase the validated lease after waiting for atomic capacity locks."""
        resource = self.resource
        ttl_seconds = int((resource.lease.expires_at - resource.lease.created_at).total_seconds())
        expiry = LeasePolicy(resource.lease.max_lifetime_seconds).initial_expiry(
            accepted_at, ttl_seconds
        )
        return ResourceLifecycle(
            replace(
                resource,
                lease=ResourceLease(accepted_at, expiry, resource.lease.max_lifetime_seconds),
                created_at=accepted_at,
            )
        )

    def request_deletion(self) -> "ResourceLifecycle":
        current = self.resource
        if current.desired_state is DesiredState.DELETED:
            return self
        return ResourceLifecycle(
            replace(
                current,
                desired_state=DesiredState.DELETED,
                status=ResourceStatus.DELETING,
                revision=current.revision + 1,
                generation=current.generation + 1,
            )
        )

    def record_status(
        self,
        target: ResourceStatus,
        *,
        deletion_confirmed: bool = False,
        outstanding_provider_operations: bool = True,
    ) -> "ResourceLifecycle":
        status = transition_status(
            self.resource.status,
            target,
            desired_state=self.resource.desired_state,
            deletion_confirmed=deletion_confirmed,
            outstanding_provider_operations=outstanding_provider_operations,
        )
        return ResourceLifecycle(replace(self.resource, status=status))

    def require_connection(self, now: datetime) -> None:
        resource = self.resource
        if (
            resource.status is not ResourceStatus.READY
            or resource.desired_state is not DesiredState.RUNNING
            or resource.lease.expires_at <= now
        ):
            raise DomainError("Resource connection is not available.")
