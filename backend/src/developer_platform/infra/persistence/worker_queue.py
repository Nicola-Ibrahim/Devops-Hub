"""Fresh, short transaction scopes for each durable worker phase."""

import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from developer_platform.application.database_lifecycle.ports import (
    DatabaseCredentials,
    DatabaseEndpoint,
    DeletionObservation,
    ProviderFailure,
    ProvisioningJob,
    ResourceCredentialCipher,
)
from developer_platform.infra.persistence.models import (
    Operation,
    ProviderOrphanRow,
    Reservation,
    Resource,
    ResourceSecret,
)
from developer_platform.infra.persistence.resource_repository import SQLAlchemyResourceRepository


class SqlAlchemyProvisioningQueue:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        installation_id: UUID,
        cipher: ResourceCredentialCipher,
        key_id: str,
    ) -> None:
        self.sessions = sessions
        self.installation_id = installation_id
        self.cipher = cipher
        self.key_id = key_id

    async def claim(self) -> ProvisioningJob | None:
        async with self.sessions() as session, session.begin():
            now = datetime.now(UTC)
            due = and_(
                Operation.next_attempt_at <= now,
                or_(
                    Operation.status == "pending",
                    and_(Operation.status == "running", Operation.claim_expires_at <= now),
                ),
            )
            resource = await session.scalar(
                select(Resource)
                .where(
                    Resource.installation_id == self.installation_id,
                    exists(select(Operation.id).where(Operation.resource_id == Resource.id, due)),
                )
                .order_by(Resource.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if resource is None:
                return None
            operation = await session.scalar(
                select(Operation)
                .where(Operation.resource_id == resource.id, due)
                .order_by((Operation.action == "delete").desc(), Operation.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if operation is None:
                return None
            if operation.action != "delete" and (
                resource.desired_state == "deleted"
                or resource.expires_at <= now
                or operation.resource_revision != resource.generation
            ):
                operation.status = "cancelled"
                if operation.attempts == 0:
                    operation.provider_outcome_uncertain = False
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource,
                    "expired" if resource.expires_at <= now else "cancelled",
                    None,
                    now,
                )
                return None
            stored = await session.get(ResourceSecret, resource.id)
            if operation.action == "provision" and stored is None:
                if resource.status not in {"pending", "provisioning"} or operation.attempts > 0:
                    operation.status = "failed"
                    operation.error_code = "credential_missing"
                    resource.status = "failed"
                    return None
                credentials = DatabaseCredentials(
                    "u_" + resource.id.hex[:20],
                    "db_" + resource.id.hex[:20],
                    secrets.token_urlsafe(32),
                    secrets.token_urlsafe(32),
                )
                stored = ResourceSecret(
                    resource_id=resource.id,
                    key_id=self.key_id,
                    ciphertext=self.cipher.encrypt(resource.id, credentials),
                )
                session.add(stored)
            elif stored is not None:
                credentials = self.cipher.decrypt(resource.id, stored.ciphertext, stored.key_id)
            else:
                credentials = DatabaseCredentials("", "", "", "")
            operation.status = "running"
            operation.claim_token = uuid4()
            operation.claim_expires_at = now + timedelta(seconds=30)
            operation.heartbeat_at = now
            operation.attempts += 1
            if operation.action in {"provision", "delete"}:
                operation.provider_outcome_uncertain = True
            if operation.action == "provision":
                resource.status = "provisioning"
            if operation.action == "delete":
                resource.status = "deleting"
            return ProvisioningJob(
                operation.id,
                resource.id,
                resource.installation_id,
                operation.resource_revision,
                operation.claim_token,
                operation.action,
                int(resource.configuration.get("cpu_millis", 500)),
                int(resource.configuration.get("memory_bytes", 536870912)),
                credentials,
            )

    async def heartbeat(self, job: ProvisioningJob) -> bool:
        async with self.sessions() as session, session.begin():
            now = datetime.now(UTC)
            operation = await session.scalar(
                select(Operation)
                .where(
                    Operation.id == job.operation_id,
                    Operation.claim_token == job.claim_token,
                    Operation.status == "running",
                    Operation.claim_expires_at > now,
                )
                .with_for_update()
            )
            if operation is None:
                return False
            operation.heartbeat_at = now
            operation.claim_expires_at = now + timedelta(seconds=30)
            return True

    async def _locked(
        self, session: AsyncSession, job: ProvisioningJob
    ) -> tuple[Resource | None, Operation | None]:
        resource = await session.scalar(
            select(Resource)
            .where(Resource.id == job.resource_id, Resource.installation_id == self.installation_id)
            .with_for_update()
        )
        operation = await session.get(Operation, job.operation_id)
        if (
            resource is None
            or operation is None
            or operation.resource_id != job.resource_id
            or operation.claim_token != job.claim_token
            or operation.status != "running"
        ):
            return None, None
        if operation.claim_expires_at is None or operation.claim_expires_at <= datetime.now(UTC):
            return None, None
        return resource, operation

    async def should_execute(self, job: ProvisioningJob) -> bool:
        async with self.sessions() as session, session.begin():
            resource, operation = await self._locked(session, job)
            if resource is None:
                return False
            assert operation is not None
            now = datetime.now(UTC)
            if job.action != "delete" and (
                resource.desired_state == "deleted"
                or resource.expires_at <= now
                or resource.generation != job.generation
            ):
                operation.status = "cancelled"
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource,
                    "expired" if resource.expires_at <= now else "cancelled",
                    None,
                    now,
                )
                return False
            return resource.generation == job.generation

    async def ready(self, job: ProvisioningJob, endpoint: DatabaseEndpoint) -> None:
        async with self.sessions() as session, session.begin():
            resource, operation = await self._locked(session, job)
            if resource is None:
                return
            assert operation is not None
            now = datetime.now(UTC)
            operation.provider_outcome_uncertain = False
            if (
                resource.desired_state == "deleted"
                or resource.expires_at <= now
                or resource.generation != job.generation
            ):
                operation.status = "cancelled"
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource,
                    "expired" if resource.expires_at <= now else "cancelled",
                    None,
                    now,
                )
                return
            resource.status = "ready"
            resource.failure_code = None
            resource.provider_id = f"dh-{resource.installation_id.hex[:8]}-{resource.id.hex}"
            resource.endpoint = {"host": endpoint.host, "port": endpoint.port}
            operation.status = "succeeded"
            operation.completed_at = now
            operation.error_code = None

    async def deleted(self, job: ProvisioningJob, observation: DeletionObservation) -> None:
        async with self.sessions() as session, session.begin():
            resource, operation = await self._locked(session, job)
            if resource is None:
                return
            assert operation is not None
            now = datetime.now(UTC)
            if resource.generation != job.generation:
                return
            pending = list(
                await session.scalars(
                    select(Operation).where(
                        Operation.resource_id == resource.id,
                        Operation.action == "provision",
                        Operation.id != operation.id,
                    )
                )
            )
            if observation.observed_owned_object:
                for previous in pending:
                    previous.provider_outcome_uncertain = False
                    if previous.status in {"pending", "running"}:
                        previous.status = "cancelled"
            uncertain = any(previous.provider_outcome_uncertain for previous in pending)
            if not observation.absent or uncertain:
                resource.status = "cleanup_failed"
                resource.failure_code = (
                    "provider_outcome_unknown" if uncertain else "cleanup_incomplete"
                )
                operation.status = "pending"
                operation.error_code = resource.failure_code
                operation.next_attempt_at = now + timedelta(seconds=15)
                return
            resource.status = "deleted"
            resource.deleted_at = now
            resource.endpoint = None
            resource.failure_code = None
            operation.status = "succeeded"
            operation.completed_at = now
            operation.provider_outcome_uncertain = False
            reservation = await session.get(Reservation, resource.id)
            if reservation is not None and reservation.released_at is None:
                reservation.released_at = now
            await session.execute(
                delete(ResourceSecret).where(ResourceSecret.resource_id == resource.id)
            )

    async def failed(self, job: ProvisioningJob, error: ProviderFailure) -> None:
        async with self.sessions() as session, session.begin():
            resource, operation = await self._locked(session, job)
            if resource is None:
                return
            assert operation is not None
            now = datetime.now(UTC)
            if resource.generation != job.generation:
                operation.status = "cancelled"
                operation.completed_at = now
                # Keep the uncertainty marker: deletion must observe the provider before
                # releasing this resource's quota or credentials.
                return
            code = error.code if re.fullmatch("[a-z_]{1,80}", error.code) else "provider_failure"
            operation.error_code = code
            operation.provider_outcome_uncertain = (
                operation.provider_outcome_uncertain or error.uncertain
            )
            if job.action == "reconcile":
                operation.status = "failed"
                operation.completed_at = now
                resource.status = "failed"
                resource.failure_code = code
            elif job.action == "delete":
                operation.status = "pending"
                operation.next_attempt_at = now + timedelta(
                    seconds=min(60, 2 ** min(operation.attempts, 5))
                )
                resource.status = "cleanup_failed"
                resource.failure_code = code
            elif operation.attempts < 5 and now < operation.deadline_at:
                operation.status = "pending"
                operation.next_attempt_at = now + timedelta(seconds=min(30, 2**operation.attempts))
            else:
                operation.status = "failed"
                operation.completed_at = now
                resource.status = "failed"
                resource.failure_code = code
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource, "provision_failed", None, now
                )

    async def sweep(self) -> None:
        async with self.sessions() as session, session.begin():
            now = datetime.now(UTC)
            resources = list(
                await session.scalars(
                    select(Resource)
                    .where(
                        Resource.installation_id == self.installation_id,
                        Resource.desired_state == "running",
                        Resource.expires_at <= now,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
            )
            for resource in resources:
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource, "expired", None, now
                )

    async def reconcile(self, resource_ids: tuple[UUID, ...]) -> None:
        async with self.sessions() as session, session.begin():
            now = datetime.now(UTC)
            # Read the complete ledger ID set independently from row locking. A resource
            # skipped because another worker owns its lock is known, not a provider orphan.
            known_ids = set(
                await session.scalars(
                    select(Resource.id).where(Resource.installation_id == self.installation_id)
                )
            )
            known = {
                row.id: row
                for row in await session.scalars(
                    select(Resource)
                    .where(Resource.installation_id == self.installation_id)
                    .with_for_update(skip_locked=True)
                )
            }
            for resource_id in resource_ids:
                if resource_id not in known_ids:
                    orphan = await session.get(ProviderOrphanRow, resource_id)
                    if orphan is None:
                        session.add(
                            ProviderOrphanRow(
                                resource_id=resource_id,
                                installation_id=self.installation_id,
                                last_seen_at=now,
                            )
                        )
                    else:
                        orphan.last_seen_at = now
                    continue
                if resource_id not in known:
                    # Its row was locked by another worker; defer this observation.
                    continue
                resource = known[resource_id]
                if resource.status == "deleted":
                    resource.status = "deleting"
                    operation = await SQLAlchemyResourceRepository(session).mark_for_deletion(
                        resource, "requested", None, now
                    )
                    operation.status = "pending"
                    operation.next_attempt_at = now
            for resource in known.values():
                if resource.status != "ready" or resource.desired_state != "running":
                    continue
                reconcile_operation = await session.scalar(
                    select(Operation).where(
                        Operation.resource_id == resource.id,
                        Operation.resource_revision == resource.generation,
                        Operation.action == "reconcile",
                    )
                )
                if reconcile_operation is None:
                    session.add(
                        Operation(
                            resource_id=resource.id,
                            resource_revision=resource.generation,
                            action="reconcile",
                            status="pending",
                            next_attempt_at=now,
                            deadline_at=now + timedelta(minutes=5),
                        )
                    )
                elif reconcile_operation.status in {"succeeded", "failed"}:
                    reconcile_operation.status = "pending"
                    reconcile_operation.next_attempt_at = now
                    reconcile_operation.deadline_at = now + timedelta(minutes=5)


class PostgresResourceEffectGuard:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def __call__(self, resource_id: UUID) -> AsyncIterator[bool]:
        key = resource_id.int % (2**63 - 1)
        async with self.engine.connect() as connection:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            )
            await connection.commit()
            try:
                yield bool(acquired)
            finally:
                if acquired:
                    try:
                        await connection.execute(
                            text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                        )
                        await connection.commit()
                    except BaseException:
                        await connection.invalidate()
                        raise
