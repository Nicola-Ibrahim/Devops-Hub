"""Safe, transport-independent domain errors."""


class DomainError(Exception):
    """Base for expected domain rule violations."""

    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LeaseViolation(DomainError):
    """A requested lease violates time or lifecycle policy."""

    code = "lease_violation"


class TransitionViolation(DomainError):
    """A requested status change violates the lifecycle state machine."""

    code = "invalid_resource_transition"
