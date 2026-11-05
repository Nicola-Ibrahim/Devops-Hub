"""Resource lifecycle vocabulary and allowed status transitions."""

from enum import StrEnum
from uuid import UUID

from developer_platform.domain.errors import TransitionViolation


def resource_action_authorized(
    *,
    project_id: UUID,
    owner_id: UUID,
    actor_project_id: UUID,
    actor_id: UUID,
    actor_role: str,
    scopes: frozenset[str],
    required_scope: str,
) -> bool:
    """Decide whether a project actor may operate on an owned resource."""
    return (
        project_id == actor_project_id
        and required_scope in scopes
        and (actor_id == owner_id or actor_role == "admin")
    )


class ResourceStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    CLEANUP_FAILED = "cleanup_failed"
    DELETED = "deleted"


class DesiredState(StrEnum):
    RUNNING = "running"
    DELETED = "deleted"


class DeletionReason(StrEnum):
    REQUESTED = "requested"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PR_CLOSED = "pr_closed"
    PROVISION_FAILED = "provision_failed"


_ALLOWED_TRANSITIONS: dict[ResourceStatus, frozenset[ResourceStatus]] = {
    ResourceStatus.PENDING: frozenset(
        {ResourceStatus.PROVISIONING, ResourceStatus.FAILED, ResourceStatus.DELETING}
    ),
    ResourceStatus.PROVISIONING: frozenset(
        {ResourceStatus.READY, ResourceStatus.FAILED, ResourceStatus.DELETING}
    ),
    ResourceStatus.READY: frozenset({ResourceStatus.FAILED, ResourceStatus.DELETING}),
    ResourceStatus.FAILED: frozenset({ResourceStatus.DELETING}),
    ResourceStatus.DELETING: frozenset({ResourceStatus.CLEANUP_FAILED, ResourceStatus.DELETED}),
    ResourceStatus.CLEANUP_FAILED: frozenset({ResourceStatus.DELETING}),
    # A reconciler may discover an anomalous late object. It must reopen cleanup.
    ResourceStatus.DELETED: frozenset({ResourceStatus.DELETING}),
}


def transition_status(
    current: ResourceStatus,
    target: ResourceStatus,
    *,
    desired_state: DesiredState,
    deletion_confirmed: bool = False,
    outstanding_provider_operations: bool = True,
) -> ResourceStatus:
    """Validate and return a new observed status.

    The caller must pass ``deletion_confirmed=True`` only after the provider has
    verified absence of all resource-owned objects and access. The default assumes
    provider operations may still be outstanding; callers may clear that condition
    only after those operations have been resolved.
    """
    if desired_state is DesiredState.DELETED and target not in {
        ResourceStatus.DELETING,
        ResourceStatus.CLEANUP_FAILED,
        ResourceStatus.DELETED,
    }:
        raise TransitionViolation(
            "A resource marked for deletion can only progress through cleanup."
        )

    if target is ResourceStatus.DELETED and desired_state is not DesiredState.DELETED:
        raise TransitionViolation("A resource must be marked for deletion before it is deleted.")

    if target is ResourceStatus.DELETED:
        if not deletion_confirmed:
            raise TransitionViolation(
                "A resource can be marked deleted only after provider absence is confirmed."
            )
        if outstanding_provider_operations:
            raise TransitionViolation(
                "A resource cannot be marked deleted while provider operations are unresolved."
            )

    if current == target:
        return current

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise TransitionViolation(
            f"Transition from {current.value} to {target.value} is not allowed."
        )

    return target
