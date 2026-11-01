"""Persistence records; schema preserved from foundation."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.persistence.base import Base, utc_now


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_resource_time", "resource_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    resource_id: Mapped[UUID | None] = mapped_column(ForeignKey("resources.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(30))
    request_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
