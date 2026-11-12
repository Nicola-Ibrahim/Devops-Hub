from urllib.parse import quote

from devops_hub.platform.application.database_lifecycle.ports import ResourceCredentialCipher
from devops_hub.platform.application.database_lifecycle.read_connection.query import (
    DatabaseConnection,
    ReadDatabaseConnection,
)
from devops_hub.platform.application.shared.errors import PlatformRequestError
from devops_hub.platform.application.shared.resource_repository import ResourceRepository


class GetDatabaseConnectionQueryHandler:
    def __init__(
        self, repository: ResourceRepository, cipher: ResourceCredentialCipher | None
    ) -> None:
        self.repository, self.cipher = repository, cipher

    async def execute(self, query: ReadDatabaseConnection) -> DatabaseConnection:
        access = query.access
        if self.cipher is None:
            raise PlatformRequestError(
                "credentials_unavailable", "Resource access is unavailable", 503
            )
        secret = await self.repository.connection(access=access, resource_id=query.resource_id)
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
