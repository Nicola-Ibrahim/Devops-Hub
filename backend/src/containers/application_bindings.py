"""Resolve an authorized resource into a short-lived private runtime binding."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from developer_platform.application.delivery import ApplicationDeliveryFailure
from developer_platform.infra.application_runtime import (
    ApplicationDatabaseBinding,
    ApplicationDatabaseBindingResolver,
    managed_resource_container_name,
)
from developer_platform.infra.credentials import FernetResourceCredentialCipher
from developer_platform.infra.persistence.delivery import ApplicationRow
from developer_platform.infra.persistence.models import Resource, ResourceSecret


class SQLAlchemyApplicationDatabaseBindings(ApplicationDatabaseBindingResolver):
    """Authorize and decrypt a ready lease in a brief, read-only SQL phase."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        installation_id: UUID,
        cipher: FernetResourceCredentialCipher,
    ) -> None:
        self.sessions = sessions
        self.installation_id = installation_id
        self.cipher = cipher

    async def resolve(
        self, project_id: UUID, application_id: UUID, resource_id: UUID
    ) -> ApplicationDatabaseBinding:
        async with self.sessions() as session, session.begin():
            now = await session.scalar(select(func.clock_timestamp()))
            if not isinstance(now, datetime):
                now = datetime.now(UTC)
            app = await session.scalar(
                select(ApplicationRow)
                .where(ApplicationRow.id == application_id)
                .with_for_update(read=True)
            )
            resource = await session.scalar(
                select(Resource)
                .where(
                    Resource.id == resource_id,
                    Resource.project_id == project_id,
                    Resource.installation_id == self.installation_id,
                    Resource.target_id == "local",
                )
                .with_for_update(read=True)
            )
            if (
                app is None
                or app.project_id != project_id
                or app.resource_id != resource_id
                or resource is None
                or resource.project_id != project_id
                or resource.installation_id != self.installation_id
                or resource.owner_id != app.owner_id
                or resource.status != "ready"
                or resource.desired_state != "running"
                or resource.expires_at <= now
                or resource.endpoint is None
                or resource.provider_id
                != managed_resource_container_name(self.installation_id, resource_id)
            ):
                raise ApplicationDeliveryFailure("resource_not_ready")
            secret = await session.get(ResourceSecret, resource_id)
            if secret is None:
                raise ApplicationDeliveryFailure("resource_not_ready")
            credentials = self.cipher.decrypt(resource_id, secret.ciphertext, secret.key_id)
            dsn = URL.create(
                # The template passes this connection URI directly to psycopg,
                # outside SQLAlchemy's ``+psycopg`` URL scheme.
                "postgresql",
                username=credentials.user,
                password=credentials.password,
                host=managed_resource_container_name(self.installation_id, resource_id),
                port=5432,
                database=credentials.database,
            ).render_as_string(hide_password=False)
            return ApplicationDatabaseBinding(
                installation_id=self.installation_id,
                project_id=project_id,
                application_id=application_id,
                resource_id=resource_id,
                container_name=managed_resource_container_name(self.installation_id, resource_id),
                dsn=dsn,
            )
