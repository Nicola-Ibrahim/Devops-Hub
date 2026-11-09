from urllib.parse import quote

from developer_platform.application.database_lifecycle.ports import ResourceCredentialCipher
from developer_platform.application.database_lifecycle.read_connection.query import (
    DatabaseConnection,
    GetDatabaseConnectionQuery,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.shared.project_access import require_project_scope
from developer_platform.domain.resource_lifecycle_repository import ResourceLifecycleRepository


class GetDatabaseConnectionQueryHandler:
    def __init__(
        self, repository: ResourceLifecycleRepository, cipher: ResourceCredentialCipher | None
    ) -> None:
        self.repository, self.cipher = repository, cipher

    async def execute(
        self, access: AccessContext, query: GetDatabaseConnectionQuery
    ) -> DatabaseConnection:
        require_project_scope(access, access.project_id, "connections:read")
        if self.cipher is None:
            raise PlatformRequestError(
                "credentials_unavailable", "Resource access is unavailable", 503
            )
        secret = await self.repository.connection(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=query.resource_id,
        )
        credentials = self.cipher.decrypt(secret.resource_id, secret.ciphertext, secret.key_id)
        hostpart = f"[{secret.host}]" if ":" in secret.host else secret.host
        return DatabaseConnection(
            connection_string=(
                f"postgresql://{quote(credentials.user, safe='')}:"
                f"{quote(credentials.password, safe='')}@{hostpart}:{secret.port}/"
                f"{quote(credentials.database, safe='')}"
            ),
            host=secret.host,
            port=secret.port,
            database=credentials.database,
            user=credentials.user,
            instructions=(
                "Connect from the configured developer host or approved tunnel. "
                "This temporary database and its stored data are removed "
                "on deletion or lease expiry."
            ),
        )
