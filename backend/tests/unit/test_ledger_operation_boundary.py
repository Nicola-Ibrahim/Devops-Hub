import asyncio
from uuid import uuid4

import pytest
from dishka import Provider, Scope, provide
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_operation_lifecycle import CapturedResponses, FakeSession

from api.platform.capabilities import PlatformRequestQueries
from containers.factory import create_container
from containers.platform_operations import PlatformHttpOperations
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.application.ledger import AcceptedDatabaseRequest
from entrypoints.http import create_app
from entrypoints.settings import Settings
from identity.contracts import AuthenticatedPrincipal
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork


def test_platform_di_binds_both_context_repositories_to_one_operation_session():
    config = Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test", token_pepper="p" * 40
    )
    container = create_container(config)

    async def run():
        try:
            async with container() as scope:
                service = await scope.get(PlatformRequestQueries)
                assert isinstance(service, PlatformHttpOperations)
                assert service.authenticate.repository._session is service.read.repository._session
                assert service.read.repository._session is service.unit.session
                await service.unit.session.close()
        finally:
            await container.close()

    asyncio.run(run())


@pytest.mark.parametrize("outcome", ["accepted", "commit_failure", "request_conflict"])
def test_http_ledger_authentication_and_commit_precede_success(outcome):
    user, project, token_id, resource_id, operation_id = (uuid4() for _ in range(5))
    events = []
    session = FakeSession(
        fail_commit=SQLAlchemyError("private database detail")
        if outcome == "commit_failure"
        else None
    )
    captured = []

    class Auth:
        async def execute(self, token):
            assert session.events == ["begin"]
            assert token == "synthetic-raw-bearer-token-for-operation"
            events.append("authenticate")
            return AuthenticatedPrincipal(
                user, project, token_id, "developer", frozenset({"resources:write"})
            )

    class Requester:
        async def execute(self, access: AccessContext, command, key):
            assert events == ["authenticate"]
            assert access.project_id == command.project_id == project
            assert access.user_id == user
            assert key == "test-request"
            captured.append(command)
            if outcome == "request_conflict":
                raise PlatformRequestError("idempotency_conflict", "Request conflicts", 409)
            return AcceptedDatabaseRequest(resource_id, operation_id)

    service = PlatformHttpOperations(Auth(), Requester(), None, SqlAlchemyUnitOfWork(session))

    class Override(Provider):
        @provide(scope=Scope.REQUEST, override=True)
        def queries(self) -> PlatformRequestQueries:
            return service

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
