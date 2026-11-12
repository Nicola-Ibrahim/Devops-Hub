"""Pure UTC lease creation and renewal policy."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from devops_platform.domain.errors import LeaseViolation
from devops_platform.domain.resources import DesiredState, ResourceStatus

_UTC = UTC
_RENEWABLE_STATUSES = frozenset(
    {ResourceStatus.PENDING, ResourceStatus.PROVISIONING, ResourceStatus.READY}
)


def _require_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LeaseViolation(f"{field} must be a timezone-aware UTC datetime.")
    if value.utcoffset() != timedelta(0):
        raise LeaseViolation(f"{field} must use UTC.")
    return value.astimezone(_UTC)


@dataclass(frozen=True, slots=True)
class LeasePolicy:
    """Lease bounds applied at request acceptance and renewal."""

    default_ttl_seconds: int = 3600
    max_lifetime_seconds: int = 86400

    def __post_init__(self) -> None:
        if (
            isinstance(self.default_ttl_seconds, bool)
            or not isinstance(self.default_ttl_seconds, int)
            or self.default_ttl_seconds <= 0
        ):
            raise LeaseViolation("Default lease duration must be a positive number of seconds.")
        if (
            isinstance(self.max_lifetime_seconds, bool)
            or not isinstance(self.max_lifetime_seconds, int)
            or self.max_lifetime_seconds <= 0
        ):
            raise LeaseViolation("Maximum lease lifetime must be a positive number of seconds.")
        if self.default_ttl_seconds > self.max_lifetime_seconds:
            raise LeaseViolation("Default lease duration cannot exceed maximum lifetime.")

    def initial_expiry(self, accepted_at: datetime, ttl_seconds: int | None = None) -> datetime:
        """Calculate expiry from acceptance time, not request submission time."""
        accepted = _require_utc(accepted_at, field="accepted_at")
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        self._validate_ttl(ttl)
        if ttl > self.max_lifetime_seconds:
            raise LeaseViolation("Requested lease exceeds the maximum lifetime.")
        return accepted + timedelta(seconds=ttl)

    def renewal_expiry(
        self,
        *,
        created_at: datetime,
        current_expiry: datetime,
        requested_expiry: datetime,
        now: datetime,
        desired_state: DesiredState,
        status: ResourceStatus,
    ) -> datetime:
        """Validate a renewal and return its normalized UTC expiry."""
        created = _require_utc(created_at, field="created_at")
        current = _require_utc(current_expiry, field="current_expiry")
        requested = _require_utc(requested_expiry, field="requested_expiry")
        current_time = _require_utc(now, field="now")

        maximum = created + timedelta(seconds=self.max_lifetime_seconds)
        if current <= created or current > maximum:
            raise LeaseViolation("Stored lease expiry is inconsistent with its creation time.")
        if current_time < created:
            raise LeaseViolation("Current time cannot precede resource creation time.")

        if desired_state is not DesiredState.RUNNING:
            raise LeaseViolation("A resource marked for deletion cannot be renewed.")
        if status not in _RENEWABLE_STATUSES:
            raise LeaseViolation("Resource status does not allow lease renewal.")
        if current <= current_time:
            raise LeaseViolation("An expired lease cannot be renewed.")
        if requested <= current:
            raise LeaseViolation("Renewal must extend the current lease expiry.")

        if requested > maximum:
            raise LeaseViolation("Requested expiry exceeds the maximum resource lifetime.")
        return requested

    @staticmethod
    def _validate_ttl(ttl_seconds: int) -> None:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise LeaseViolation("Lease duration must be an integer number of seconds.")
        if ttl_seconds <= 0:
            raise LeaseViolation("Lease duration must be positive.")
