from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateInternalUserCommand:
    user_name: str
    password: str = field(repr=False)
    actor_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class BootstrapFirstProjectAdminCommand:
    user_id: UUID
    project_id: UUID


@dataclass(frozen=True, slots=True)
class SetInternalUserActiveCommand:
    actor_id: UUID
    user_id: UUID
    active: bool


@dataclass(frozen=True, slots=True)
class IssuePasswordSetupCommand:
    user_id: UUID
    actor_id: UUID


@dataclass(frozen=True, slots=True)
class ConsumePasswordSetupCommand:
    secret: str = field(repr=False)
    new_password: str = field(repr=False)
