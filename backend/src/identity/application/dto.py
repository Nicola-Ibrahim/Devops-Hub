from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class IssueTokenCommand:
    user_name: str
    project_name: str
    hours: int = 24
    scopes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class PreparedApiToken:
    """Private completion result, never an HTTP inventory response."""

    token_id: UUID
    secret: str = field(repr=False)
