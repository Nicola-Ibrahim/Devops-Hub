"""Persistence records owned by application generation and delivery workflows."""

import hashlib
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from devops_hub.platform.application.shared.dto import AccessContext
from devops_hub.platform.application.shared.errors import PlatformRequestError
from devops_hub.platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentSpec,
)
from devops_hub.platform.application.workload_delivery.create_workload.command import (
    ApplicationRegistration,
)
from devops_hub.platform.application.workload_delivery.deploy_workload.command import (
    DeploymentSpec,
)
from devops_hub.platform.application.workload_delivery.shared.models import (
    ApplicationDetails,
    DeliveryClaim,
    DeliveryResult,
    DeliveryStepDetails,
    DeploymentDetails,
    RegisteredRepository,
)
from devops_hub.platform.domain.aggregates.application_delivery import ApplicationDelivery
from devops_hub.platform.domain.entities.application import Application, DeliveryStep
from devops_hub.platform.domain.errors import DomainError
from devops_hub.platform.domain.interfaces.application_repository import ApplicationRepository
from devops_hub.platform.infra.persistence.models import (
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    Resource,
)
from shared.infra.persistence.base import Base, utc_now


class ApplicationRow(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','ready','failed','deleting','deleted')", name="status"
        ),
        UniqueConstraint("project_id", "name", name="uq_application_project_name"),
        Index("ix_applications_project_updated", "project_id", "updated_at"),
        Index("ix_applications_preview", "source_repository", "pull_request"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project_registrations.project_id"))
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("project_environments.id"))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    template_id: Mapped[str] = mapped_column(String(64))
    template_version: Mapped[str] = mapped_column(String(32))
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    source_repository: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pull_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApplicationDeliveryStepRow(Base):
    __tablename__ = "application_delivery_steps"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('repository','resource','deployment','template_update','preview_cleanup')",
            name="kind",
        ),
        CheckConstraint("status IN ('pending','running','succeeded','failed')", name="status"),
        CheckConstraint("attempts >= 0", name="attempts"),
        UniqueConstraint("idempotency_key", name="uq_application_delivery_step_key"),
        Index("ix_application_delivery_due", "status", "next_attempt_at", "claim_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(200))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    claim_token: Mapped[UUID | None]
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApplicationDeliveryIdempotencyRow(Base):
    __tablename__ = "application_delivery_idempotency"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "route", "key", name="uq_app_delivery_scope"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project_registrations.project_id"))
    route: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"))
    result_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApplicationDeploymentRow(Base):
    __tablename__ = "application_deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','deleted')", name="status"
        ),
        Index("ix_application_deployments_history", "application_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    image_digest: Mapped[str] = mapped_column(String(300))
    target_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApplicationWebhookEventRow(Base):
    __tablename__ = "application_webhook_events"

    delivery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(80))
    repository: Mapped[str] = mapped_column(String(200))
    pull_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# SQL repository operations share the persistence module with their table mappings.
def _application(row: ApplicationRow) -> ApplicationDetails:
    return ApplicationDetails(
        id=row.id,
        project_id=row.project_id,
        environment_id=row.environment_id,
        owner_id=row.owner_id,
        name=row.name,
        template_id=row.template_id,
        template_version=row.template_version,
        repository_url=row.repository_url,
        resource_id=row.resource_id,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_preview=row.is_preview,
        source_repository=row.source_repository,
        pull_request=row.pull_request,
        expires_at=row.expires_at,
    )


def _step(row: ApplicationDeliveryStepRow) -> DeliveryStepDetails:
    return DeliveryStepDetails(
        id=row.id,
        application_id=row.application_id,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        attempts=row.attempts,
        error_code=row.error_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _deployment(row: ApplicationDeploymentRow) -> DeploymentDetails:
    return DeploymentDetails(
        id=row.id,
        application_id=row.application_id,
        image_digest=row.image_digest,
        target_id=row.target_id,
        status=row.status,  # type: ignore[arg-type]
        url=row.url,
        created_at=row.created_at,
    )


def _domain_application(row: ApplicationRow) -> Application:
    return Application(
        id=row.id,
        project_id=row.project_id,
        environment_id=row.environment_id,
        owner_id=row.owner_id,
        name=row.name,
        template_id=row.template_id,
        template_version=row.template_version,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        resource_id=row.resource_id,
    )


def _domain_step(row: ApplicationDeliveryStepRow) -> DeliveryStep:
    return DeliveryStep(
        id=row.id,
        application_id=row.application_id,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        attempts=row.attempts,
        created_at=row.created_at,
        updated_at=row.updated_at,
        error_code=row.error_code,
    )


class SQLAlchemyApplicationDeliveryRepository(ApplicationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_for_update(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDelivery | None:
        application = await self.session.scalar(
            select(ApplicationRow)
            .where(
                ApplicationRow.id == application_id,
                ApplicationRow.project_id == project_id,
            )
            .with_for_update()
        )
        if application is None:
            return None
        steps = await self.session.scalars(
            select(ApplicationDeliveryStepRow)
            .where(ApplicationDeliveryStepRow.application_id == application_id)
            .order_by(ApplicationDeliveryStepRow.created_at, ApplicationDeliveryStepRow.id)
            .with_for_update()
        )
        return ApplicationDelivery(
            _domain_application(application), tuple(_domain_step(step) for step in steps)
        )

    async def save(self, delivery: ApplicationDelivery) -> None:
        application = await self.session.scalar(
            select(ApplicationRow)
            .where(ApplicationRow.id == delivery.application.id)
            .with_for_update()
        )
        if application is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        application.status = delivery.application.status
        application.updated_at = delivery.application.updated_at
        for step in delivery.steps:
            row = await self.session.scalar(
                select(ApplicationDeliveryStepRow)
                .where(
                    ApplicationDeliveryStepRow.id == step.id,
                    ApplicationDeliveryStepRow.application_id == application.id,
                )
                .with_for_update()
            )
            if row is None:
                raise PlatformRequestError(
                    "delivery_step_not_found", "Delivery step was not found", 404
                )
            row.status = step.status
            row.attempts = step.attempts
            row.error_code = step.error_code
            row.updated_at = step.updated_at

    async def create_application(
        self,
        access: AccessContext,
        command: ApplicationRegistration,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[ApplicationDetails, bool]:
        project = await self.session.scalar(
            select(ProjectRegistrationRow)
            .where(ProjectRegistrationRow.project_id == access.project_id)
            .with_for_update()
        )
        environment = await self.session.scalar(
            select(ProjectEnvironmentRow).where(
                ProjectEnvironmentRow.id == command.environment_id,
                ProjectEnvironmentRow.project_id == access.project_id,
            )
        )
        if project is None or environment is None or not project.configured:
            raise PlatformRequestError(
                "project_not_configured", "Project environment is not configured", 409
            )
        previous = await self._idempotency(access, "applications:create", idempotency_key)
        if previous is not None:
            if previous.request_hash != request_hash:
                raise PlatformRequestError(
                    "idempotency_conflict", "Idempotency-Key was used for a different request", 409
                )
            application = await self.session.get(ApplicationRow, previous.application_id)
            if application is None:
                raise PlatformRequestError(
                    "application_not_found", "Application was not found", 404
                )
            return _application(application), True
        row = ApplicationRow(
            id=uuid4(),
            project_id=access.project_id,
            environment_id=command.environment_id,
            owner_id=access.user_id,
            name=command.name,
            template_id=command.template_id,
            template_version=command.template_version,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        self.session.add(
            ApplicationDeliveryIdempotencyRow(
                user_id=access.user_id,
                project_id=access.project_id,
                route="applications:create",
                key=idempotency_key,
                request_hash=request_hash,
                application_id=row.id,
                created_at=now,
            )
        )
        self.session.add(
            ApplicationDeliveryStepRow(
                id=uuid4(),
                application_id=row.id,
                kind="repository",
                status="pending",
                idempotency_key=f"application:{row.id}:repository",
                request_payload={},
                attempts=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        return _application(row), False

    async def list_applications(self, project_id: UUID) -> tuple[ApplicationDetails, ...]:
        rows = await self.session.scalars(
            select(ApplicationRow)
            .where(ApplicationRow.project_id == project_id)
            .order_by(ApplicationRow.updated_at.desc(), ApplicationRow.id)
            .limit(100)
        )
        return tuple(_application(row) for row in rows)

    async def find_application(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDetails | None:
        row = await self.session.scalar(
            select(ApplicationRow).where(
                ApplicationRow.id == application_id,
                ApplicationRow.project_id == project_id,
            )
        )
        return _application(row) if row is not None else None

    async def list_steps(self, application_id: UUID) -> tuple[DeliveryStepDetails, ...]:
        rows = await self.session.scalars(
            select(ApplicationDeliveryStepRow)
            .where(ApplicationDeliveryStepRow.application_id == application_id)
            .order_by(ApplicationDeliveryStepRow.created_at, ApplicationDeliveryStepRow.id)
        )
        return tuple(_step(row) for row in rows)

    async def enqueue_resource_attachment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentSpec,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeliveryStepDetails:
        app = await self._owned_application(access, application_id, write=True)
        previous = await self._idempotency(
            access, f"applications:{application_id}:resource", idempotency_key
        )
        if previous is not None:
            if previous.request_hash != request_hash:
                raise PlatformRequestError(
                    "idempotency_conflict", "Idempotency-Key was used for a different request", 409
                )
            row = await self.session.get(ApplicationDeliveryStepRow, previous.result_id)
            if row is None:
                raise PlatformRequestError(
                    "delivery_step_not_found", "Delivery step was not found", 404
                )
            return _step(row)
        if app.resource_id is not None:
            raise PlatformRequestError(
                "resource_already_attached", "Application already has a database", 409
            )
        row = ApplicationDeliveryStepRow(
            id=uuid4(),
            application_id=app.id,
            kind="resource",
            status="pending",
            idempotency_key=f"application:{app.id}:resource:{idempotency_key}",
            request_payload={
                "template_id": command.template_id,
                "version": command.version,
                "target_id": command.target_id,
                "size_id": command.size_id,
                "ttl_seconds": command.ttl_seconds,
            },
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        await self._record_idempotency(
            access,
            f"applications:{application_id}:resource",
            idempotency_key,
            request_hash,
            app.id,
            row.id,
            now,
        )
        return _step(row)

    async def enqueue_deployment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentSpec,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeploymentDetails:
        app = await self._owned_application(access, application_id, write=True)
        route = f"applications:{application_id}:deployment"
        previous = await self._idempotency(access, route, idempotency_key)
        if previous is not None:
            if previous.request_hash != request_hash:
                raise PlatformRequestError(
                    "idempotency_conflict", "Idempotency-Key was used for a different request", 409
                )
            deployment = await self.session.get(ApplicationDeploymentRow, previous.result_id)
            if deployment is None:
                raise PlatformRequestError("deployment_not_found", "Deployment was not found", 404)
            return _deployment(deployment)
        deployment = ApplicationDeploymentRow(
            id=uuid4(),
            application_id=app.id,
            requested_by=access.user_id,
            image_digest=command.image_digest,
            target_id=command.target_id,
            status="pending",
            created_at=now,
        )
        self.session.add(deployment)
        await self.session.flush()
        step = ApplicationDeliveryStepRow(
            id=uuid4(),
            application_id=app.id,
            kind="deployment",
            status="pending",
            idempotency_key=f"application:{app.id}:deployment:{deployment.id}",
            request_payload={
                "deployment_id": str(deployment.id),
                "image_digest": command.image_digest,
                "target_id": command.target_id,
                "resource_id": str(app.resource_id) if app.resource_id else None,
            },
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(step)
        await self._record_idempotency(
            access, route, idempotency_key, request_hash, app.id, deployment.id, now
        )
        return _deployment(deployment)

    async def deployment_history(
        self, project_id: UUID, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        rows = await self.session.scalars(
            select(ApplicationDeploymentRow)
            .join(ApplicationRow, ApplicationRow.id == ApplicationDeploymentRow.application_id)
            .where(
                ApplicationDeploymentRow.application_id == application_id,
                ApplicationRow.project_id == project_id,
            )
            .order_by(ApplicationDeploymentRow.created_at.desc())
        )
        return tuple(_deployment(row) for row in rows)

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID, now: datetime
    ) -> DeliveryStepDetails:
        app = await self._owned_application(access, application_id, write=True, allow_closed=True)
        row = await self.session.scalar(
            select(ApplicationDeliveryStepRow)
            .where(
                ApplicationDeliveryStepRow.id == step_id,
                ApplicationDeliveryStepRow.application_id == application_id,
            )
            .with_for_update()
        )
        if row is None:
            raise PlatformRequestError(
                "delivery_step_not_found", "Delivery step was not found", 404
            )
        if row.status == "succeeded":
            return _step(row)
        if row.kind != "preview_cleanup" and (
            app.status in {"deleting", "deleted"}
            or (app.expires_at is not None and app.expires_at <= now)
        ):
            raise PlatformRequestError(
                "application_closed", "Application cleanup is in progress or complete", 409
            )
        if (
            row.status == "running"
            and row.claim_expires_at is not None
            and row.claim_expires_at > now
        ):
            raise PlatformRequestError(
                "delivery_step_running", "Delivery step is still running", 409
            )
        try:
            updated_delivery = ApplicationDelivery(
                _domain_application(app), (_domain_step(row),)
            ).retry(row.id, now)
        except DomainError as exc:
            raise PlatformRequestError(
                "application_closed", "Application cleanup is in progress or complete", 409
            ) from exc
        updated_application = updated_delivery.application
        updated_step = updated_delivery.steps[0]
        row.status = updated_step.status
        row.error_code = updated_step.error_code
        row.next_attempt_at = now
        row.claim_token = None
        row.claim_expires_at = None
        row.updated_at = updated_step.updated_at
        app.status = updated_application.status
        app.updated_at = updated_application.updated_at
        if row.kind == "deployment":
            deployment_id = row.request_payload.get("deployment_id")
            if deployment_id:
                deployment = await self.session.get(
                    ApplicationDeploymentRow, UUID(str(deployment_id))
                )
                if deployment is not None:
                    deployment.status = "pending"
                    deployment.completed_at = None
        return _step(row)

    async def record_webhook(
        self,
        *,
        delivery_id: str,
        payload_hash: str,
        event: str,
        repository: str,
        pull_request: int | None,
        action: str,
        now: datetime,
    ) -> bool:
        inserted = await self.session.scalar(
            insert(ApplicationWebhookEventRow)
            .values(
                delivery_id=delivery_id,
                payload_hash=payload_hash,
                event=event,
                repository=repository,
                pull_request=pull_request,
                action=action,
                accepted=False,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=[ApplicationWebhookEventRow.delivery_id])
            .returning(ApplicationWebhookEventRow.delivery_id)
        )
        if inserted is not None:
            return True
        previous = await self.session.get(ApplicationWebhookEventRow, delivery_id)
        if previous is None or previous.payload_hash != payload_hash:
            raise PlatformRequestError(
                "webhook_replay_conflict",
                "Webhook delivery conflicts with a previously recorded event",
                409,
            )
        return False

    async def find_registered_repository(self, repository: str) -> RegisteredRepository | None:
        row = await self.session.scalar(
            select(ProjectRegistrationRow).where(
                ProjectRegistrationRow.repository.ilike(repository),
                ProjectRegistrationRow.configured.is_(True),
            )
        )
        if row is None:
            return None
        environment_id = await self.session.scalar(
            select(ProjectEnvironmentRow.id)
            .where(ProjectEnvironmentRow.project_id == row.project_id)
            .order_by(ProjectEnvironmentRow.name)
            .limit(1)
        )
        if environment_id is None:
            return None
        return RegisteredRepository(row.project_id, environment_id, repository)

    async def request_preview(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        repository: str,
        pull_request: int,
        branch: str,
        head_sha: str,
        image_digest: str | None,
        template_id: str,
        template_version: str,
        ttl_seconds: int,
        now: datetime,
    ) -> UUID | None:
        registration = await self.session.scalar(
            select(ProjectRegistrationRow).where(
                ProjectRegistrationRow.project_id == project_id,
                ProjectRegistrationRow.repository.ilike(repository),
                ProjectRegistrationRow.configured.is_(True),
            )
        )
        if registration is None:
            return None
        environment_id = await self.session.scalar(
            select(ProjectEnvironmentRow.id)
            .where(ProjectEnvironmentRow.project_id == project_id)
            .order_by(ProjectEnvironmentRow.name)
            .limit(1)
        )
        if environment_id is None:
            return None
        repository_key = hashlib.sha256(repository.encode()).hexdigest()[:12]
        name = f"preview-{repository_key}-{pull_request}"
        app = await self.session.scalar(
            select(ApplicationRow)
            .where(
                ApplicationRow.project_id == project_id,
                ApplicationRow.source_repository == repository,
                ApplicationRow.pull_request == pull_request,
                ApplicationRow.is_preview.is_(True),
            )
            .with_for_update()
        )
        if app is None:
            app = ApplicationRow(
                id=uuid4(),
                project_id=project_id,
                environment_id=environment_id,
                owner_id=owner_id,
                name=name,
                template_id=template_id,
                template_version=template_version,
                status="pending",
                is_preview=True,
                source_repository=repository,
                pull_request=pull_request,
                source_branch=branch,
                source_sha=head_sha,
                expires_at=now + timedelta(seconds=ttl_seconds),
                created_at=now,
                updated_at=now,
            )
            self.session.add(app)
            await self.session.flush()
            self.session.add(
                ApplicationDeliveryStepRow(
                    id=uuid4(),
                    application_id=app.id,
                    kind="resource",
                    status="pending",
                    idempotency_key=(
                        f"preview:{repository_key}:{pull_request}:resource:{head_sha}"
                    ),
                    request_payload={
                        "template_id": "postgres",
                        "version": "16",
                        "target_id": "local",
                        "size_id": "small",
                        "ttl_seconds": ttl_seconds,
                    },
                    attempts=0,
                    next_attempt_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            if app.status == "deleting":
                raise PlatformRequestError(
                    "preview_cleanup_pending", "Retry the reopen event after cleanup finishes", 409
                )
            app.source_branch = branch
            app.source_sha = head_sha
            app.expires_at = now + timedelta(seconds=ttl_seconds)
            app.updated_at = now
            if app.status == "deleted":
                app.status = "pending"
                app.resource_id = None
                self.session.add(
                    ApplicationDeliveryStepRow(
                        id=uuid4(),
                        application_id=app.id,
                        kind="resource",
                        status="pending",
                        idempotency_key=(
                            f"preview:{repository_key}:{pull_request}:resource:{head_sha}:{uuid4().hex}"
                        ),
                        request_payload={
                            "template_id": "postgres",
                            "version": "16",
                            "target_id": "local",
                            "size_id": "small",
                            "ttl_seconds": ttl_seconds,
                        },
                        attempts=0,
                        next_attempt_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
        if image_digest:
            existing_step = await self.session.scalar(
                select(ApplicationDeliveryStepRow).where(
                    ApplicationDeliveryStepRow.application_id == app.id,
                    ApplicationDeliveryStepRow.kind == "deployment",
                    ApplicationDeliveryStepRow.request_payload["image_digest"].astext
                    == image_digest,
                )
            )
            if existing_step is None:
                deployment = ApplicationDeploymentRow(
                    id=uuid4(),
                    application_id=app.id,
                    requested_by=owner_id,
                    image_digest=image_digest,
                    target_id="local",
                    status="pending",
                    created_at=now,
                )
                self.session.add(deployment)
                await self.session.flush()
                self.session.add(
                    ApplicationDeliveryStepRow(
                        id=uuid4(),
                        application_id=app.id,
                        kind="deployment",
                        status="pending",
                        idempotency_key=(
                            f"preview:{repository_key}:{pull_request}:deployment:{head_sha}"
                        ),
                        request_payload={
                            "deployment_id": str(deployment.id),
                            "image_digest": image_digest,
                            "target_id": "local",
                            "resource_id": str(app.resource_id) if app.resource_id else None,
                        },
                        attempts=0,
                        next_attempt_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return app.id

    async def close_preview(self, *, repository: str, pull_request: int, now: datetime) -> int:
        apps = await self.session.scalars(
            select(ApplicationRow)
            .where(
                ApplicationRow.source_repository == repository,
                ApplicationRow.pull_request == pull_request,
                ApplicationRow.is_preview.is_(True),
                ApplicationRow.status != "deleted",
            )
            .with_for_update()
        )
        count = 0
        for app in apps:
            app.status = "deleting"
            app.updated_at = now
            # Pending work has not crossed the external-effect boundary. Prevent it
            # from starting after closure; running work remains fenced and must finish
            # or be recovered before cleanup can be claimed.
            pending = await self.session.scalars(
                select(ApplicationDeliveryStepRow).where(
                    ApplicationDeliveryStepRow.application_id == app.id,
                    ApplicationDeliveryStepRow.kind != "preview_cleanup",
                    ApplicationDeliveryStepRow.status == "pending",
                    ApplicationDeliveryStepRow.attempts == 0,
                )
            )
            for step in pending:
                step.status = "failed"
                step.error_code = "preview_closed"
                step.updated_at = now
                if step.kind == "deployment":
                    deployment_id = step.request_payload.get("deployment_id")
                    if deployment_id:
                        deployment = await self.session.get(
                            ApplicationDeploymentRow, UUID(str(deployment_id))
                        )
                        if deployment is not None:
                            deployment.status = "failed"
                            deployment.completed_at = now
            await self._queue_preview_cleanup(app, now)
            count += 1
        return count

    async def expire_previews(self, now: datetime, limit: int) -> int:
        apps = await self.session.scalars(
            select(ApplicationRow)
            .where(
                ApplicationRow.is_preview.is_(True),
                ApplicationRow.status != "deleted",
                ApplicationRow.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        count = 0
        for app in apps:
            app.status = "deleting"
            app.updated_at = now
            await self._queue_preview_cleanup(app, now)
            count += 1
        return count

    async def claim_step(self, now: datetime, lease_seconds: int) -> DeliveryClaim | None:
        due = and_(
            ApplicationDeliveryStepRow.next_attempt_at <= now,
            or_(
                ApplicationDeliveryStepRow.status == "pending",
                and_(
                    ApplicationDeliveryStepRow.status == "running",
                    ApplicationDeliveryStepRow.claim_expires_at <= now,
                ),
            ),
        )
        candidates = await self.session.scalars(
            select(ApplicationDeliveryStepRow.id)
            .where(due)
            .order_by(
                ApplicationDeliveryStepRow.next_attempt_at, ApplicationDeliveryStepRow.created_at
            )
            .limit(100)
        )
        for step_id in candidates:
            # Lock order is application -> step across close, expiry, claim and
            # completion. The initial query only gathers IDs; both rows are
            # revalidated under locks before a claim is issued.
            app = await self.session.scalar(
                select(ApplicationRow)
                .where(
                    ApplicationRow.id
                    == select(ApplicationDeliveryStepRow.application_id)
                    .where(ApplicationDeliveryStepRow.id == step_id)
                    .scalar_subquery()
                )
                .with_for_update(skip_locked=True)
            )
            if app is None:
                continue
            step = await self.session.scalar(
                select(ApplicationDeliveryStepRow)
                .where(
                    ApplicationDeliveryStepRow.id == step_id,
                    ApplicationDeliveryStepRow.application_id == app.id,
                )
                .with_for_update(skip_locked=True)
            )
            if step is None:
                continue
            if not (
                step.next_attempt_at <= now
                and (
                    step.status == "pending"
                    or (
                        step.status == "running"
                        and step.claim_expires_at is not None
                        and step.claim_expires_at <= now
                    )
                )
            ):
                continue
            if not await self._dependencies_succeeded(step):
                continue
            if step.kind == "preview_cleanup":
                unresolved = await self.session.scalar(
                    select(ApplicationDeliveryStepRow.id)
                    .where(
                        ApplicationDeliveryStepRow.application_id == app.id,
                        ApplicationDeliveryStepRow.kind != "preview_cleanup",
                        ApplicationDeliveryStepRow.status.in_(("pending", "running")),
                    )
                    .limit(1)
                )
                if unresolved is not None:
                    continue
            elif app.status in {"deleting", "deleted"}:
                # Pending attempts>0 are retries of effects already started; replay
                # with the same key to recover their stable result. Never start a new
                # step after closure.
                if step.status != "running" and not (
                    step.status == "pending" and step.attempts > 0
                ):
                    step.status = "failed"
                    step.error_code = "preview_closed"
                    step.updated_at = now
                    continue
            elif app.expires_at is not None and app.expires_at <= now:
                app.status = "deleting"
                app.updated_at = now
                if step.status == "pending" and step.attempts == 0:
                    step.status = "failed"
                    step.error_code = "preview_expired"
                    step.updated_at = now
                    await self._queue_preview_cleanup(app, now)
                    continue
            step.status = "running"
            step.attempts += 1
            step.claim_token = uuid4()
            step.claim_expires_at = now + timedelta(seconds=lease_seconds)
            step.heartbeat_at = now
            step.updated_at = now
            payload = dict(step.request_payload)
            if step.kind == "deployment" and payload.get("resource_id") is None:
                payload["resource_id"] = str(app.resource_id) if app.resource_id else None
            return DeliveryClaim(
                step_id=step.id,
                application_id=app.id,
                project_id=app.project_id,
                environment_id=app.environment_id,
                owner_id=app.owner_id,
                application_name=app.name,
                template_id=app.template_id,
                template_version=app.template_version,
                kind=step.kind,  # type: ignore[arg-type]
                idempotency_key=step.idempotency_key,
                claim_token=step.claim_token,
                attempts=step.attempts,
                payload=payload,
            )
        return None

    async def effect_is_current(self, claim: DeliveryClaim, now: datetime) -> bool:
        step, app = await self._claimed_rows(claim, now)
        return step is not None and app is not None

    async def heartbeat_step(self, claim: DeliveryClaim, now: datetime, lease_seconds: int) -> bool:
        result = await self.session.execute(
            update(ApplicationDeliveryStepRow)
            .where(
                ApplicationDeliveryStepRow.id == claim.step_id,
                ApplicationDeliveryStepRow.status == "running",
                ApplicationDeliveryStepRow.claim_token == claim.claim_token,
                ApplicationDeliveryStepRow.claim_expires_at > now,
            )
            .values(
                heartbeat_at=now,
                claim_expires_at=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        )
        return bool(getattr(result, "rowcount", 0))

    async def complete_step(
        self, claim: DeliveryClaim, result: DeliveryResult, now: datetime
    ) -> bool:
        step, app = await self._claimed_rows(claim, now)
        if step is None or app is None:
            return False
        step.error_code = None
        step.claim_token = None
        step.claim_expires_at = None
        step.updated_at = now
        if claim.kind == "repository":
            step.status = "succeeded"
            app.repository_url = result.repository_url
        elif claim.kind == "resource":
            if result.resource_id is None:
                raise PlatformRequestError(
                    "delivery_result_invalid", "Resource step returned no resource", 500
                )
            resource = await self.session.scalar(
                select(Resource).where(
                    Resource.id == result.resource_id,
                    Resource.project_id == app.project_id,
                    Resource.environment_id == app.environment_id,
                    Resource.owner_id == app.owner_id,
                )
            )
            if resource is None:
                raise PlatformRequestError(
                    "resource_not_found", "Requested resource was not found", 404
                )
            app.resource_id = result.resource_id
            if app.is_preview and app.status == "deleting":
                # A close/expiry raced the external request. Its stable ID is now
                # durable and cleanup can safely own deletion.
                step.status = "succeeded"
                await self._queue_preview_cleanup(app, now)
            elif resource.status == "ready" and resource.desired_state == "running":
                step.status = "succeeded"
            else:
                # Keep deployments blocked until the durable resource row is ready.
                step.status = "pending"
                step.next_attempt_at = now + timedelta(seconds=5)
        elif claim.kind == "deployment":
            deployment_id = result.deployment_id
            if deployment_id is None:
                raise PlatformRequestError(
                    "delivery_result_invalid", "Deployment result is missing", 500
                )
            deployment = await self.session.get(ApplicationDeploymentRow, deployment_id)
            if deployment is None or deployment.application_id != app.id:
                return False
            step.status = "succeeded"
            deployment.status = "succeeded"
            deployment.url = result.deployment_url
            deployment.provider_reference = result.provider_reference
            deployment.completed_at = now
            if app.status != "deleting":
                app.status = "ready"
        elif claim.kind == "preview_cleanup":
            step.status = "succeeded"
            app.status = "deleted"
            app.resource_id = None
        elif claim.kind == "template_update":
            step.status = "succeeded"
        app.updated_at = now
        return True

    async def fail_step(
        self,
        claim: DeliveryClaim,
        error_code: str,
        now: datetime,
        retry_after_seconds: int,
        retryable: bool,
    ) -> bool:
        step, app = await self._claimed_rows(claim, now)
        if step is None or app is None:
            return False
        step.error_code = error_code
        step.claim_token = None
        step.claim_expires_at = None
        step.updated_at = now
        if claim.kind == "preview_cleanup":
            # Cleanup is a safety obligation, so continue polling with capped
            # backoff instead of reaching a terminal state after five attempts.
            step.status = "pending"
            step.next_attempt_at = now + timedelta(seconds=min(300, 2 ** min(step.attempts, 8)))
            app.status = "deleting"
        elif retryable and (step.attempts < 5 or error_code == "application_busy"):
            step.status = "pending"
            step.next_attempt_at = now + timedelta(seconds=retry_after_seconds)
        else:
            step.status = "failed"
            if app.status != "deleting":
                app.status = "failed"
            if claim.kind == "deployment":
                deployment_id = step.request_payload.get("deployment_id")
                if deployment_id:
                    deployment = await self.session.get(
                        ApplicationDeploymentRow, UUID(str(deployment_id))
                    )
                    if deployment is not None:
                        deployment.status = "failed"
                        deployment.completed_at = now
        app.updated_at = now
        return True

    async def _idempotency(
        self, access: AccessContext, route: str, key: str
    ) -> ApplicationDeliveryIdempotencyRow | None:
        return cast(
            ApplicationDeliveryIdempotencyRow | None,
            await self.session.scalar(
                select(ApplicationDeliveryIdempotencyRow).where(
                    ApplicationDeliveryIdempotencyRow.user_id == access.user_id,
                    ApplicationDeliveryIdempotencyRow.project_id == access.project_id,
                    ApplicationDeliveryIdempotencyRow.route == route,
                    ApplicationDeliveryIdempotencyRow.key == key,
                ),
            ),
        )

    async def _record_idempotency(
        self,
        access: AccessContext,
        route: str,
        key: str,
        request_hash: str,
        application_id: UUID,
        result_id: UUID,
        now: datetime,
    ) -> None:
        self.session.add(
            ApplicationDeliveryIdempotencyRow(
                user_id=access.user_id,
                project_id=access.project_id,
                route=route,
                key=key,
                request_hash=request_hash,
                application_id=application_id,
                result_id=result_id,
                created_at=now,
            )
        )

    async def _owned_application(
        self, access: AccessContext, application_id: UUID, write: bool, allow_closed: bool = False
    ) -> ApplicationRow:
        app = await self.session.scalar(
            select(ApplicationRow)
            .where(
                ApplicationRow.id == application_id,
                ApplicationRow.project_id == access.project_id,
            )
            .with_for_update(read=not write)
        )
        if app is None or (access.user_id != app.owner_id and access.role != "admin"):
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        if write and not allow_closed and app.status in {"deleting", "deleted"}:
            raise PlatformRequestError(
                "application_closed", "Application cleanup is in progress or complete", 409
            )
        return app

    async def _dependencies_succeeded(self, step: ApplicationDeliveryStepRow) -> bool:
        if step.kind in {"deployment", "resource", "template_update"}:
            repository_step = await self.session.scalar(
                select(ApplicationDeliveryStepRow.id).where(
                    ApplicationDeliveryStepRow.application_id == step.application_id,
                    ApplicationDeliveryStepRow.kind == "repository",
                    ApplicationDeliveryStepRow.status != "succeeded",
                )
            )
            if repository_step is not None:
                return False
        if step.kind == "deployment":
            resource_step = await self.session.scalar(
                select(ApplicationDeliveryStepRow.id).where(
                    ApplicationDeliveryStepRow.application_id == step.application_id,
                    ApplicationDeliveryStepRow.kind == "resource",
                    ApplicationDeliveryStepRow.status != "succeeded",
                )
            )
            if resource_step is not None:
                return False
        return True

    async def _claimed_rows(
        self, claim: DeliveryClaim, now: datetime
    ) -> tuple[ApplicationDeliveryStepRow | None, ApplicationRow | None]:
        app = await self.session.scalar(
            select(ApplicationRow)
            .where(ApplicationRow.id == claim.application_id)
            .with_for_update()
        )
        if app is None:
            return None, None
        step = await self.session.scalar(
            select(ApplicationDeliveryStepRow)
            .where(
                ApplicationDeliveryStepRow.id == claim.step_id,
                ApplicationDeliveryStepRow.application_id == claim.application_id,
                ApplicationDeliveryStepRow.status == "running",
                ApplicationDeliveryStepRow.claim_token == claim.claim_token,
                ApplicationDeliveryStepRow.claim_expires_at > now,
            )
            .with_for_update()
        )
        return (step, app) if step is not None else (None, None)

    async def _queue_preview_cleanup(self, app: ApplicationRow, now: datetime) -> None:
        existing_cleanup = await self.session.scalar(
            select(ApplicationDeliveryStepRow)
            .where(
                ApplicationDeliveryStepRow.application_id == app.id,
                ApplicationDeliveryStepRow.kind == "preview_cleanup",
            )
            .order_by(ApplicationDeliveryStepRow.created_at.desc())
            .with_for_update()
        )
        deployment_steps = await self.session.scalars(
            select(ApplicationDeliveryStepRow).where(
                ApplicationDeliveryStepRow.application_id == app.id,
                ApplicationDeliveryStepRow.kind == "deployment",
            )
        )
        remove_deployments = any(
            step.status in {"succeeded", "running"} or step.attempts > 0
            for step in deployment_steps
        )
        payload = {
            "resource_id": (
                str(app.resource_id)
                if app.resource_id
                else (
                    existing_cleanup.request_payload.get("resource_id")
                    if existing_cleanup is not None
                    else None
                )
            ),
            "remove_deployments": (
                remove_deployments
                or bool(
                    existing_cleanup is not None
                    and existing_cleanup.request_payload.get("remove_deployments")
                )
            ),
        }
        if existing_cleanup is not None:
            if existing_cleanup.status in {"failed", "succeeded"}:
                existing_cleanup.status = "pending"
                existing_cleanup.next_attempt_at = now
            if existing_cleanup.status == "pending":
                existing_cleanup.request_payload = {**existing_cleanup.request_payload, **payload}
                existing_cleanup.updated_at = now
            return
        self.session.add(
            ApplicationDeliveryStepRow(
                id=uuid4(),
                application_id=app.id,
                kind="preview_cleanup",
                status="pending",
                idempotency_key=f"application:{app.id}:preview-cleanup:{uuid4().hex}",
                request_payload=payload,
                attempts=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )
