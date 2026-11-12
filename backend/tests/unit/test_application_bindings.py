"""Authorization and transaction lifetime tests for database runtime bindings."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from devops_platform.application.application_delivery.shared.ports import (
    ApplicationDeliveryFailure,
)
from devops_platform.application.resource_lifecycle.ports import DatabaseCredentials
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import Select

from devops_platform.infra.persistence.application_bindings import (
    SQLAlchemyApplicationDatabaseBindings,
)
from devops_platform.infra.persistence.delivery import ApplicationRow
from devops_platform.infra.persistence.models import Resource, ResourceSecret
from devops_platform.infra.providers.application_runtime import managed_resource_container_name


class FakeSession:
    def __init__(self, app: object, resource: object | None, secret: object | None) -> None:
        self.app, self.resource, self.secret = app, resource, secret
        self.active = False
        self.statements: list[Select[tuple[object]]] = []
        self.exited = False

    async def __aenter__(self):
        self.active = True
        return self

    async def __aexit__(self, *_args):
        self.active = False
        self.exited = True

    def begin(self):
        return self

    async def scalar(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return datetime.now(UTC)
        entity = statement.column_descriptions[0].get("entity")
        if entity is ApplicationRow:
            return self.app
        if entity is Resource:
            return self.resource
        raise AssertionError(f"Unexpected scalar query for {entity}")

    async def get(self, entity, _key):
        assert entity is ResourceSecret
        return self.secret


class FakeSessions:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


class CheckingCipher:
    def __init__(self, session: FakeSession, credentials: DatabaseCredentials) -> None:
        self.session = session
        self.credentials = credentials
        self.was_inside_transaction = False

    def decrypt(self, *_args):
        self.was_inside_transaction = self.session.active
        return self.credentials


def _records(installation_id, project_id, app_id, owner_id, resource_id):
    resource_name = managed_resource_container_name(installation_id, resource_id)
    app = SimpleNamespace(
        id=app_id,
        project_id=project_id,
        owner_id=owner_id,
        resource_id=resource_id,
    )
    resource = SimpleNamespace(
        id=resource_id,
        installation_id=installation_id,
        project_id=project_id,
        owner_id=owner_id,
        status="ready",
        desired_state="running",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        target_id="local",
        provider_id=resource_name,
        endpoint={"host": "127.0.0.1", "port": 5432},
    )
    secret = SimpleNamespace(
        resource_id=resource_id,
        key_id="test-key",
        ciphertext=b"opaque-ciphertext",
    )
    return app, resource, secret


def test_database_binding_decrypts_inside_short_app_then_resource_read_transaction() -> None:
    install, project, app_id, owner, resource_id = (uuid4() for _ in range(5))
    app, resource, secret = _records(install, project, app_id, owner, resource_id)
    session = FakeSession(app, resource, secret)
    credentials = DatabaseCredentials("feature_user", "feature_db", "private-pass", "admin")
    cipher = CheckingCipher(session, credentials)
    resolver = SQLAlchemyApplicationDatabaseBindings(
        FakeSessions(session),
        install,
        cipher,  # type: ignore[arg-type]
    )

    binding = asyncio.run(resolver.resolve(project, app_id, resource_id))

    dsn = conninfo_to_dict(binding.dsn)
    assert dsn["user"] == credentials.user
    assert dsn["password"] == credentials.password
    assert dsn["host"] == managed_resource_container_name(install, resource_id)
    assert binding.application_id == app_id
    assert cipher.was_inside_transaction
    assert session.exited
    app_select = session.statements[1]
    resource_select = session.statements[2]
    assert app_select._for_update_arg is not None and app_select._for_update_arg.read
    assert resource_select._for_update_arg is not None and resource_select._for_update_arg.read


@pytest.mark.parametrize("failure", ["wrong_project", "wrong_owner", "expired", "not_ready"])
def test_database_binding_rejects_unowned_or_unavailable_resource(failure: str) -> None:
    install, project, app_id, owner, resource_id = (uuid4() for _ in range(5))
    app, resource, secret = _records(install, project, app_id, owner, resource_id)
    if failure == "wrong_project":
        resource.project_id = uuid4()
    elif failure == "wrong_owner":
        resource.owner_id = uuid4()
    elif failure == "expired":
        resource.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    else:
        resource.status = "provisioning"
    session = FakeSession(app, resource, secret)
    cipher = CheckingCipher(session, DatabaseCredentials("user", "db", "private", "admin"))
    resolver = SQLAlchemyApplicationDatabaseBindings(
        FakeSessions(session),
        install,
        cipher,  # type: ignore[arg-type]
    )

    with pytest.raises(ApplicationDeliveryFailure, match="resource_not_ready"):
        asyncio.run(resolver.resolve(project, app_id, resource_id))
    assert not cipher.was_inside_transaction
    assert session.exited
