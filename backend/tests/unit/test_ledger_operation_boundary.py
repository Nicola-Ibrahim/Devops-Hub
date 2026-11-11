import asyncio
from uuid import uuid4

import pytest
from developer_platform.application.resource_requests.submit_database_request.result import (
    AcceptedDatabaseRequest,
)
from dishka import Provider, Scope, provide
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_operation_lifecycle import CapturedResponses, FakeSession

from developer_platform.application.database_provisioning.read_resources.handler import (
    ReadResourcesHandler,
)
from developer_platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.module import IdentityModule
from identity.contracts import AuthenticatedPrincipal
from infra.composition.factory import create_container
from infra.http.app import create_app
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.settings import Settings


def test_platform_di_binds_both_context_repositories_to_one_operation_session():
    config = Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test", token_pepper="p" * 40
    )
    container = create_container(config)

    async def run():
        try:
            async with container() as scope:
                request = await scope.get(RequestTemporaryDatabaseHandler)
                read = await scope.get(ReadResourcesHandler)
                unit = await scope.get(SqlAlchemyUnitOfWork)
                assert request.repository._session is read.repository._session
                assert read.repository._session is unit.session
                await unit.session.close()
        finally:
            await container.close()

    asyncio.run(run())


@pytest.mark.parametrize("outcome", ["accepted", "commit_failure", "request_conflict"])
def test_http_ledger_authentication_and_commit_precede_success(outcome, monkeypatch):
    user, project, token_id, resource_id, operation_id = (uuid4() for _ in range(5))
    events = []
    session = FakeSession(
        fail_commit=SQLAlchemyError("private database detail")
        if outcome == "commit_failure"
        else None
    )
    captured = []

    class Identity:
        async def query(self, query):
            assert query == AuthenticateApiTokenQuery("synthetic-raw-bearer-token-for-operation")
            return AuthenticatedPrincipal(
                user, project, token_id, "developer", frozenset({"resources:write"})
            )

    async def authenticate(active_session, token, settings, clock):
        assert active_session is session
        assert session.events == ["begin"]
        assert token == "synthetic-raw-bearer-token-for-operation"
        events.append("authenticate")
        return AccessContext(user, project, "developer", frozenset({"resources:write"}))

    monkeypatch.setattr("infra.http.platform_module.authenticate_request", authenticate)

    class Requester:
        async def execute(self, message):
            access, command, key = message.access, message.request, message.idempotency_key
            assert events == ["authenticate"]
            assert access.project_id == command.project_id == project
            assert access.user_id == user
            assert key == "test-request"
            captured.append(command)
            if outcome == "request_conflict":
                raise PlatformRequestError("idempotency_conflict", "Request conflicts", 409)
            return AcceptedDatabaseRequest(resource_id, operation_id)

    requester = Requester()
    unit = SqlAlchemyUnitOfWork(session)

    class Override(Provider):
        @provide(scope=Scope.REQUEST, override=True)
        def identity(self) -> IdentityModule:
            return Identity()

        @provide(scope=Scope.REQUEST, override=True)
        def unit(self) -> SqlAlchemyUnitOfWork:
            return unit

        @provide(scope=Scope.REQUEST, override=True)
        def request_handler(self) -> RequestTemporaryDatabaseHandler:
            return requester

    config = Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test", token_pepper="p" * 40
    )
    container = create_container(config, overrides=(Override(),))
    capture = CapturedResponses(create_app(container=container))
    try:
        with TestClient(capture) as client:
            response = client.post(
                "/api/v1/resources",
                headers={
                    "Authorization": "Bearer synthetic-raw-bearer-token-for-operation",
                    "Idempotency-Key": "test-request",
                },
                json={
                    "project_id": str(project),
                    "environment_id": str(uuid4()),
                    "version": "16",
                    "display_name": "test-db",
                    "template_id": "postgres",
                    "target_id": "local",
                    "size_id": "small",
                    "ttl_seconds": 3600,
                },
            )
        expected = {"accepted": 202, "commit_failure": 503, "request_conflict": 409}[outcome]
        assert response.status_code == expected
        assert capture.statuses == [expected]
        assert len(captured) == 1
        assert "private database" not in response.text
        assert session.events[-1] == "close"
        if outcome == "accepted":
            assert session.events == ["begin", "commit", "close"]
            assert response.json()["operation_id"] == str(operation_id)
        else:
            assert "rollback" in session.events
    finally:
        asyncio.run(container.close())
