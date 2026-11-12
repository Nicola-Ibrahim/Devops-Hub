"""Application resources use the same current-authority, quota and replay ledger."""

import asyncio
from uuid import UUID, uuid4

import pytest
from developer_platform.application.application_delivery.attach_resource.command import (
    ResourceAttachmentSpec,
)
from developer_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from test_foundation_postgres import async_engine_for, client_for, issue

from composition.integrations.application_resources import LedgerApplicationResources
from developer_platform.application.resource_catalog.catalog import ApprovedPostgresCatalog
from developer_platform.application.resource_catalog.models import PostgresOption
from developer_platform.infra.persistence.models import QuotaBudget, Reservation, Resource
from identity.infra.persistence.models import ProjectMembershipRow

pytestmark = pytest.mark.postgres


def test_attachment_replays_and_cleanup_keeps_reservation_until_worker_confirms(
    postgres_engine, tmp_path
):
    _, token = issue(postgres_engine, tmp_path / "credential")
    with client_for(postgres_engine) as client:
        project = client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer " + token}
        ).json()[0]
    project_id, environment = UUID(project["project_id"]), UUID(project["environments"][0]["id"])
    with Session(postgres_engine) as session, session.begin():
        owner = session.scalar(
            select(ProjectMembershipRow.user_id).where(
                ProjectMembershipRow.project_id == project_id
            )
        )
        session.add(
            QuotaBudget(
                scope="target",
                scope_id="local",
                max_resources=2,
                max_cpu_millis=2000,
                max_memory_bytes=2**31,
                max_storage_bytes=2**32,
            )
        )
    database = async_engine_for(postgres_engine)
    adapter = LedgerApplicationResources(
        async_sessionmaker(database, expire_on_commit=False),
        ApprovedPostgresCatalog((PostgresOption(requestable=True, unavailable_reason=None),)),
        uuid4(),
    )

    async def exercise():
        kwargs = dict(
            project_id=project_id,
            environment_id=environment,
            owner_id=owner,
            command=ResourceAttachmentSpec("postgres", "16", "local", "small", 3600),
            idempotency_key="application:resource:stable-key",
        )
        first = await adapter.request(**kwargs)
        assert await adapter.request(**kwargs) == first
        assert not await adapter.ready(project_id, first)
        with pytest.raises(ApplicationDeliveryFailure, match="resource_cleanup_pending"):
            await adapter.delete(project_id, owner, first, "cleanup")
        with Session(postgres_engine) as session:
            assert session.scalar(select(func.count()).select_from(Resource)) == 1
            assert session.get(Resource, first).desired_state == "deleted"
            assert session.get(Reservation, first).released_at is None
        with Session(postgres_engine) as session, session.begin():
            session.delete(session.get(ProjectMembershipRow, (owner, project_id)))
        with pytest.raises(ApplicationDeliveryFailure, match="resource_owner_not_authorized"):
            await adapter.request(**kwargs)

    try:
        asyncio.run(exercise())
    finally:
        asyncio.run(database.dispose())
