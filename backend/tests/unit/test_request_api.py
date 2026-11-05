"""HTTP contract tests for platform resource request and read routes."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.platform.capabilities import PlatformRequestQueries
from api.platform.schemas import (
    AcceptedOperation,
    OperationView,
    ProjectRegistrationView,
    ResourcePage,
    ResourceRequest,
    ResourceView,
)
from containers.http import create_app
from developer_platform.application.errors import PlatformRequestError
from identity.domain.errors import AuthenticationRejected

PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
ENVIRONMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
RESOURCE_ID = UUID("33333333-3333-4333-8333-333333333333")
OPERATION_ID = UUID("44444444-4444-4444-8444-444444444444")
OWNER_ID = UUID("55555555-5555-4555-8555-555555555555")
TOKEN = "t" * 43
NOW = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def _request_payload() -> dict[str, object]:
    return {
        "project_id": str(PROJECT_ID),
        "environment_id": str(ENVIRONMENT_ID),
        "version": "16",
        "display_name": "feature-db",
        "template_id": "postgres",
        "target_id": "local",
        "size_id": "small",
        "ttl_seconds": 1800,
    }


class FakePlatformQueries:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.errors: dict[str, Exception] = {}

    def _authorize(self, token: str | None) -> None:
        if token != TOKEN:
            raise AuthenticationRejected()

    def _raise_error(self, route: str) -> None:
        error = self.errors.get(route)
        if error is not None:
            raise error

    async def request_database(self, token, command, key) -> AcceptedOperation:
        self._authorize(token)
        self._raise_error("request")
        self.calls.append(("request_database", token, command, key))
        return AcceptedOperation(resource_id=RESOURCE_ID, operation_id=OPERATION_ID)

    async def projects(self, token):
        return [await self.project(token, PROJECT_ID)]

    async def project(self, token, project_id) -> ProjectRegistrationView:
        self._authorize(token)
        self._raise_error("project")
        self.calls.append(("project", token, project_id))
        return ProjectRegistrationView(
            project_id=PROJECT_ID,
            name="demo",
            owning_team_id=uuid4(),
            owning_team_name="platform",
            repository="example/demo",
            configured=True,
            environments=[{"id": ENVIRONMENT_ID, "name": "dev"}],
        )

    async def resources(self, token, project_id, after, limit) -> ResourcePage:
        self._authorize(token)
        self._raise_error("resources")
        self.calls.append(("resources", token, project_id, after, limit))
        return ResourcePage(
            items=[self._resource()],
            next_after=RESOURCE_ID if limit < 100 else None,
        )

    async def resource(self, token, resource_id) -> ResourceView:
        self._authorize(token)
        self._raise_error("resource")
        self.calls.append(("resource", token, resource_id))
        return self._resource()

    async def operation(self, token, operation_id) -> OperationView:
        self._authorize(token)
        self._raise_error("operation")
        self.calls.append(("operation", token, operation_id))
        return OperationView(
            id=OPERATION_ID,
            resource_id=RESOURCE_ID,
            action="provision",
            status="pending",
            attempts=0,
            next_attempt_at=NOW,
        )

    @staticmethod
    def _resource() -> ResourceView:
        return ResourceView(
            id=RESOURCE_ID,
            project_id=PROJECT_ID,
            owner_id=OWNER_ID,
            environment_id=ENVIRONMENT_ID,
            display_name="feature-db",
            template_id="postgres",
            target_id="local",
            size_id="small",
            desired_state="running",
            status="pending",
            revision=1,
            created_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )


class ApiOnlyPlatformProvider(Provider):
    def __init__(self, queries: FakePlatformQueries) -> None:
        super().__init__()
        self.queries = queries

    @provide(scope=Scope.REQUEST)
    def platform_queries(self) -> PlatformRequestQueries:
        return self.queries


def _client(queries: FakePlatformQueries) -> tuple[TestClient, object]:
    container = make_async_container(ApiOnlyPlatformProvider(queries), FastapiProvider())
    return TestClient(create_app(container=container)), container


def test_request_resource_returns_accepted_operation_and_forwards_private_inputs():
    queries = FakePlatformQueries()
    client, container = _client(queries)
    key = "feature-branch:42"
    try:
        with client:
            response = client.post(
                "/api/v1/resources",
                headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": key},
                json=_request_payload(),
            )

        assert response.status_code == 202
        assert response.headers["location"] == f"/api/v1/operations/{OPERATION_ID}"
        assert response.json() == {
            "resource_id": str(RESOURCE_ID),
            "operation_id": str(OPERATION_ID),
        }
        name, token, command, forwarded_key = queries.calls[0]
        assert name == "request_database"
        assert token == TOKEN
        assert command.project_id == PROJECT_ID
        assert command.environment_id == ENVIRONMENT_ID
        assert forwarded_key == key
    finally:
        asyncio.run(container.close())


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": f"Bearer {TOKEN}"},
        {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "invalid key"},
    ],
)
def test_request_requires_valid_idempotency_key(headers):
    queries = FakePlatformQueries()
    client, container = _client(queries)
    try:
        with client:
            response = client.post("/api/v1/resources", headers=headers, json=_request_payload())
        assert response.status_code == 422
        assert queries.calls == []
    finally:
        asyncio.run(container.close())


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", str(OWNER_ID)),
        ("image", "unapproved/image:latest"),
        ("work_reference", {"repository": "someone/else", "branch": "main"}),
    ],
)
def test_request_contract_rejects_client_selected_owner_images_and_work_references(field, value):
    payload = _request_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ResourceRequest.model_validate(payload)


@pytest.mark.parametrize("field", ["environment_id", "version"])
def test_request_contract_requires_environment_and_version(field):
    payload = _request_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        ResourceRequest.model_validate(payload)


def test_platform_read_routes_return_project_resource_page_and_operation_schemas():
    queries = FakePlatformQueries()
    client, container = _client(queries)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        with client:
            projects = client.get("/api/v1/projects", headers=headers)
            project = client.get(f"/api/v1/projects/{PROJECT_ID}", headers=headers)
            page = client.get(f"/api/v1/projects/{PROJECT_ID}/resources?limit=10", headers=headers)
            resource = client.get(f"/api/v1/resources/{RESOURCE_ID}", headers=headers)
            operation = client.get(f"/api/v1/operations/{OPERATION_ID}", headers=headers)

        assert project.status_code == page.status_code == resource.status_code == 200
        assert operation.status_code == projects.status_code == 200
        assert [item["project_id"] for item in projects.json()] == [str(PROJECT_ID)]
        assert project.json()["environments"] == [{"id": str(ENVIRONMENT_ID), "name": "dev"}]
        assert page.json()["items"][0]["status"] == "pending"
        assert resource.json()["owner_id"] == str(OWNER_ID)
        assert operation.json()["status"] == "pending"
        assert not {"dsn", "password", "credentials", "ciphertext"} & set(resource.json())
        assert [call[0] for call in queries.calls] == [
            "project",
            "project",
            "resources",
            "resource",
            "operation",
        ]
        assert all(call[1] == TOKEN for call in queries.calls)
    finally:
        asyncio.run(container.close())


@pytest.mark.parametrize("authorization", [None, "Basic invalid"])
def test_platform_routes_share_bearer_authentication_errors(authorization):
    queries = FakePlatformQueries()
    client, container = _client(queries)
    headers = {} if authorization is None else {"Authorization": authorization}
    try:
        with client:
            response = client.get(f"/api/v1/projects/{PROJECT_ID}", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["request_id"] == response.headers["x-request-id"]
    finally:
        asyncio.run(container.close())


@pytest.mark.parametrize(
    "route,error,status",
    [
        (
            "request",
            PlatformRequestError("idempotency_conflict", "Request conflicts with prior state", 409),
            409,
        ),
        ("project", PlatformRequestError("not_found", "Resource or project not found", 404), 404),
    ],
)
def test_expected_platform_errors_are_sanitized_correlated_and_uncacheable(route, error, status):
    queries = FakePlatformQueries()
    queries.errors[route] = error
    client, container = _client(queries)
    try:
        with client:
            if route == "request":
                response = client.post(
                    "/api/v1/resources",
                    headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "key-1"},
                    json=_request_payload(),
                )
            else:
                response = client.get(
                    f"/api/v1/projects/{PROJECT_ID}", headers={"Authorization": f"Bearer {TOKEN}"}
                )
        assert response.status_code == status
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert response.json()["code"] == error.code
        assert "SELECT" not in response.text
        assert "password" not in response.text
    finally:
        asyncio.run(container.close())


def test_resource_collection_pagination_is_bounded_by_http_contract():
    queries = FakePlatformQueries()
    client, container = _client(queries)
    try:
        with client:
            response = client.get(
                f"/api/v1/projects/{PROJECT_ID}/resources?limit=101",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
        assert response.status_code == 422
        assert queries.calls == []
    finally:
        asyncio.run(container.close())


if __name__ == "__main__":
    pytest.main([__file__])
