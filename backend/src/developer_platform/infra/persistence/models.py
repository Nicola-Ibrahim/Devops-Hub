"""Persistence records; schema preserved from foundation."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.persistence.base import Base, utc_now


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("desired_state IN ('running', 'deleted')", name="desired_state"),
        CheckConstraint(
            "status IN ('pending','provisioning','ready','failed','deleting',"
            "'cleanup_failed','deleted')",
            name="status",
        ),
        CheckConstraint("revision >= 1 AND generation >= 1", name="positive_revisions"),
        CheckConstraint("expires_at > created_at", name="positive_lease"),
        CheckConstraint(
            "deletion_reason IS NULL OR deletion_reason IN "
            "('requested','expired','cancelled','pr_closed','provision_failed')",
            name="deletion_reason",
        ),
        Index("ix_resources_project_status", "project_id", "status"),
        Index("ix_resources_expiry", "desired_state", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    display_name: Mapped[str] = mapped_column(String(100))
    template_id: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    size_id: Mapped[str] = mapped_column(String(50))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB)
    work_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    desired_state: Mapped[str] = mapped_column(String(20), default="running")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    installation_id: Mapped[UUID]
    provider_id: Mapped[str | None] = mapped_column(String(255))
    endpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    deletion_reason: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (
        CheckConstraint("action IN ('provision','delete','reconcile')", name="action"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')", name="status"
        ),
        CheckConstraint("attempts >= 0 AND resource_revision >= 1", name="attempt_revision"),
        UniqueConstraint("resource_id", "resource_revision", "action", name="uq_operation_intent"),
        Index("ix_operations_due", "status", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resources.id"))
    resource_revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None]
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_outcome_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "route", "key", name="uq_idempotency_scope"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    route: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resources.id"))
    operation_id: Mapped[UUID] = mapped_column(ForeignKey("operations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuotaBudget(Base):
    """One row per project or target; later workflows lock rows in a fixed order."""

    __tablename__ = "quota_budgets"
    __table_args__ = (
        CheckConstraint("scope IN ('project','target')", name="scope"),
        CheckConstraint(
            "max_resources >= 0 AND max_cpu_millis >= 0 AND max_memory_bytes >= 0 "
            "AND max_storage_bytes >= 0",
            name="nonnegative",
        ),
    )

    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    max_resources: Mapped[int] = mapped_column(Integer)
    max_cpu_millis: Mapped[int] = mapped_column(Integer)
    max_memory_bytes: Mapped[int] = mapped_column(BigInteger)
    max_storage_bytes: Mapped[int] = mapped_column(BigInteger)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "cpu_millis >= 0 AND memory_bytes >= 0 AND storage_bytes >= 0", name="nonnegative"
        ),
    )

    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    cpu_millis: Mapped[int] = mapped_column(Integer)
    memory_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_bytes: Mapped[int] = mapped_column(BigInteger)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResourceSecret(Base):
    __tablename__ = "resource_secrets"

    resource_id: Mapped[UUID] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    key_id: Mapped[str] = mapped_column(String(100))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
