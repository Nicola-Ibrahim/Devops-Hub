"""PostgreSQL persistence checks for durable resource-worker recovery semantics."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from developer_platform.application.resource_lifecycle.ports import (
    DatabaseCredentials,
    DatabaseEndpoint,
    DeletionObservation,
    ProviderFailure,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for

from developer_platform.domain.leases import LeasePolicy
from developer_platform.domain.resources import DesiredState, ResourceStatus
from developer_platform.infra.persistence.models import (
    Operation,
    ProjectEnvironmentRow,
    ProjectRegistrationRow,
    ProviderOrphanRow,
    QuotaBudget,
    Reservation,
    Resource,
    ResourceSecret,
)
from developer_platform.infra.persistence.resource_repository import SQLAlchemyResourceRepository
from developer_platform.infra.persistence.worker_queue import SqlAlchemyProvisioningQueue
from developer_platform.infra.security.credentials import FernetResourceCredentialCipher
from identity.infra.persistence.models import InternalUserRow, ProjectRow, TeamRow

pytestmark = pytest.mark.postgres
KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


def seed_resource(engine, *, status="pending", expires_in=3600, action="provision"):
    user_id, project_id, team_id = uuid4(), uuid4(), uuid4()
    installation_id, resource_id, environment_id = uuid4(), uuid4(), uuid4()
    operation_id, now = uuid4(), datetime.now(UTC)
    created_at = now + timedelta(seconds=expires_in - 10) if expires_in <= 0 else now
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                InternalUserRow(id=user_id, name=f"worker-user-{user_id}"),
                ProjectRow(id=project_id, name=f"worker-project-{project_id}"),
                TeamRow(id=team_id, name=f"worker-team-{team_id}"),
            ]
        )
        session.flush()
        session.add(
            ProjectRegistrationRow(
                project_id=project_id,
                name=f"worker-project-{project_id}",
                owning_team_id=team_id,
                owning_team_name="platform",
                repository="org/worker-test",
                configured=True,
            )
        )
        session.flush()
        session.add(ProjectEnvironmentRow(id=environment_id, project_id=project_id, name="test"))
        session.flush()
        resource = Resource(
            id=resource_id,
            environment_id=environment_id,
            owner_id=user_id,
            project_id=project_id,
            display_name="worker-test-db",
            template_id="postgres",
            target_id="local",
            size_id="small",
            configuration={
                "cpu_millis": 500,
                "memory_bytes": 536870912,
                "max_lifetime_seconds": 7200,
            },
            work_reference=None,
            desired_state="running",
            status=status,
            revision=1,
            generation=1,
            installation_id=installation_id,
            provider_id=None,
            endpoint=None,
            failure_code=None,
            deletion_reason=None,
            created_at=created_at,
            expires_at=now + timedelta(seconds=expires_in),
            deleted_at=None,
        )
        session.add(resource)
        session.flush()
        session.add(
            Operation(
                id=operation_id,
                resource_id=resource_id,
                resource_revision=1,
                action=action,
                status="pending",
                attempts=0,
                next_attempt_at=now,
                deadline_at=now + timedelta(hours=1),
                claim_token=None,
                claim_expires_at=None,
                heartbeat_at=None,
                provider_outcome_uncertain=False,
                error_code=None,
                created_at=now,
                completed_at=None,
            )
        )
        session.add(
            Reservation(
                resource_id=resource_id,
                cpu_millis=500,
                memory_bytes=536870912,
                storage_bytes=1073741824,
                released_at=None,
            )
        )
        session.add(
            QuotaBudget(
                scope="project",
                scope_id=str(project_id),
                max_resources=3,
                max_cpu_millis=2000,
                max_memory_bytes=2147483648,
                max_storage_bytes=4294967296,
            )
        )
    return installation_id, resource_id, operation_id, created_at


def queue_for(engine, installation_id):
    database = async_engine_for(engine)
    queue = SqlAlchemyProvisioningQueue(
        async_sessionmaker(database, expire_on_commit=False),
        installation_id,
        FernetResourceCredentialCipher(KEY, "test-key"),
        "test-key",
    )
    return database, queue


def test_expired_worker_claim_is_recovered_with_same_encrypted_credentials(postgres_engine):
    installation_id, _, operation_id, _ = seed_resource(postgres_engine)
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        first = asyncio.run(queue.claim())
        assert first is not None
        with Session(postgres_engine) as session, session.begin():
            operation = session.get(Operation, operation_id)
            operation.claim_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        second = asyncio.run(queue.claim())
        assert second is not None
        assert second.claim_token != first.claim_token
        assert second.credentials == first.credentials
        with Session(postgres_engine) as session:
            stored = session.get(ResourceSecret, first.resource_id)
            assert stored is not None
            assert first.credentials.password.encode() not in stored.ciphertext
    finally:
        asyncio.run(database.dispose())


def test_stale_failure_cannot_overwrite_new_generation_or_clear_uncertainty(postgres_engine):
    installation_id, resource_id, _, _ = seed_resource(postgres_engine)
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        job = asyncio.run(queue.claim())
        assert job is not None
        with Session(postgres_engine) as session, session.begin():
            resource = session.get(Resource, resource_id)
            resource.generation = 2
            resource.revision = 2
            resource.status = "deleting"
            before = (resource.status, resource.failure_code, resource.desired_state)
        asyncio.run(queue.failed(job, ProviderFailure("late_failure", uncertain=False)))
        with Session(postgres_engine) as session:
            resource = session.get(Resource, resource_id)
            operation = session.get(Operation, job.operation_id)
            assert (resource.status, resource.failure_code, resource.desired_state) == before
            assert operation.status == "cancelled"
            assert operation.provider_outcome_uncertain is True
    finally:
        asyncio.run(database.dispose())


def test_late_provision_completion_cannot_override_delete_intent(postgres_engine):
    installation_id, resource_id, _, _ = seed_resource(postgres_engine)
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        job = asyncio.run(queue.claim())
        assert job is not None

        async def request_deletion():
            async with AsyncSession(database) as session, session.begin():
                resource = await session.get(Resource, resource_id, with_for_update=True)
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource, "requested", None, datetime.now(UTC)
                )

        asyncio.run(request_deletion())
        asyncio.run(queue.ready(job, DatabaseEndpoint("127.0.0.1", 54321)))
        with Session(postgres_engine) as session:
            resource = session.get(Resource, resource_id)
            provision = session.get(Operation, job.operation_id)
            deletion = session.scalar(
                select(Operation).where(
                    Operation.resource_id == resource_id,
                    Operation.action == "delete",
                )
            )
            assert resource.status == "deleting"
            assert resource.desired_state == "deleted"
            assert resource.endpoint is None
            assert provision.status == "cancelled"
            assert deletion is not None and deletion.status == "pending"
    finally:
        asyncio.run(database.dispose())


def test_renewal_changes_lease_revision_but_does_not_fence_provision_generation(
    postgres_engine,
):
    installation_id, resource_id, _, created_at = seed_resource(postgres_engine)
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        job = asyncio.run(queue.claim())
        assert job is not None
        with Session(postgres_engine) as session, session.begin():
            resource = session.get(Resource, resource_id)
            resource.expires_at = LeasePolicy(max_lifetime_seconds=7200).renewal_expiry(
                created_at=created_at,
                current_expiry=resource.expires_at.astimezone(UTC),
                requested_expiry=created_at + timedelta(hours=2),
                now=datetime.now(UTC),
                desired_state=DesiredState(resource.desired_state),
                status=ResourceStatus.PROVISIONING,
            )
            resource.revision += 1
        assert asyncio.run(queue.should_execute(job)) is True
    finally:
        asyncio.run(database.dispose())


def test_delete_releases_reservation_only_after_confirmed_absence_and_unknown_resolution(
    postgres_engine,
):
    installation_id, resource_id, _, _ = seed_resource(postgres_engine, status="ready")
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        with Session(postgres_engine) as session, session.begin():
            provision = session.scalar(
                select(Operation).where(
                    Operation.resource_id == resource_id, Operation.action == "provision"
                )
            )
            provision.status = "succeeded"
            provision.provider_outcome_uncertain = False

        # Create the generation-fenced deletion intent through the lifecycle helper.
        async def request_deletion():
            async with AsyncSession(database) as session, session.begin():
                resource = await session.get(Resource, resource_id, with_for_update=True)
                await SQLAlchemyResourceRepository(session).mark_for_deletion(
                    resource, "requested", None, datetime.now(UTC)
                )

        asyncio.run(request_deletion())
        delete_job = asyncio.run(queue.claim())
        assert delete_job is not None and delete_job.action == "delete"
        with Session(postgres_engine) as session, session.begin():
            provision = session.scalar(
                select(Operation).where(
                    Operation.resource_id == resource_id, Operation.action == "provision"
                )
            )
            provision.provider_outcome_uncertain = True
            session.add(
                ResourceSecret(
                    resource_id=resource_id,
                    key_id="test-key",
                    ciphertext=FernetResourceCredentialCipher(KEY, "test-key").encrypt(
                        resource_id,
                        DatabaseCredentials("user", "database", "password", "admin"),
                    ),
                )
            )
        asyncio.run(
            queue.deleted(
                delete_job,
                DeletionObservation(absent=True, observed_owned_object=False),
            )
        )
        with Session(postgres_engine) as session:
            assert session.get(Resource, resource_id).status == "cleanup_failed"
            assert session.get(Reservation, resource_id).released_at is None

        # Owned-object observation resolves the uncertain provision attempt, but absence
        # must still be confirmed before quota and encrypted credentials are released.
        with Session(postgres_engine) as session, session.begin():
            delete_op = session.get(Operation, delete_job.operation_id)
            delete_op.status = "pending"
            delete_op.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        retry = asyncio.run(queue.claim())
        assert retry is not None and retry.action == "delete"
        asyncio.run(
            queue.deleted(
                retry,
                DeletionObservation(absent=True, observed_owned_object=True),
            )
        )
        with Session(postgres_engine) as session:
            assert session.get(Resource, resource_id).status == "deleted"
            assert session.get(Reservation, resource_id).released_at is not None
            assert session.get(ResourceSecret, resource_id) is None
    finally:
        asyncio.run(database.dispose())


def test_expiry_sweep_tracks_expired_resources_and_orphans_without_false_orphan(
    postgres_engine,
):
    installation_id, resource_id, _, _ = seed_resource(postgres_engine, expires_in=-5)
    database, queue = queue_for(postgres_engine, installation_id)
    orphan_id = uuid4()
    try:
        asyncio.run(queue.sweep())
        asyncio.run(queue.reconcile((resource_id, orphan_id)))
        with Session(postgres_engine) as session:
            resource = session.get(Resource, resource_id)
            assert resource.desired_state == "deleted"
            assert resource.status == "deleting"
            orphan = session.get(ProviderOrphanRow, orphan_id)
            assert orphan is not None and orphan.installation_id == installation_id
            assert orphan_id != resource.id
    finally:
        asyncio.run(database.dispose())


def test_reconcile_does_not_call_a_skip_locked_ledger_resource_an_orphan(postgres_engine):
    installation_id, resource_id, _, _ = seed_resource(postgres_engine)
    database, queue = queue_for(postgres_engine, installation_id)
    try:
        with Session(postgres_engine) as locker, locker.begin():
            resource = locker.scalar(
                select(Resource).where(Resource.id == resource_id).with_for_update()
            )
            assert resource is not None
            asyncio.run(queue.reconcile((resource_id,)))
            with Session(postgres_engine) as check:
                assert check.get(ProviderOrphanRow, resource_id) is None
    finally:
        asyncio.run(database.dispose())
