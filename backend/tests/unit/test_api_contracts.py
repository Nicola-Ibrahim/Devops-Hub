from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Query
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app import create_api
from api.dependencies import ApiServices
from api.platform.schemas import RenewRequest, ResourceRequest, ResourceView
from bootstrap.http import create_app
from bootstrap.settings import Settings
from developer_platform.application.catalog import ReadCatalog
from identity.application.authenticate import Authenticate
from identity.domain.credentials import CredentialSnapshot
from identity.infra.tokens import token_digest


def settings():
    return Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test",
        token_pepper="unit-test-pepper-" * 3,
        database_connect_timeout=1,
    )


def test_liveness_and_openapi_do_not_connect_or_migrate():
    with TestClient(create_app(settings())) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        spec = client.get("/openapi.json").json()
        assert spec["paths"]["/api/v1/me"]["get"]["security"] == [{"HTTPBearer": []}]
        assert "/api/v1/resources" not in spec["paths"]
        assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize("header", [None, "Bearer short", "Basic not-a-token"])
def test_missing_or_malformed_identity_fails_before_database_access(header):
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/me", headers={"Authorization": header} if header else {})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"


def test_database_errors_do_not_echo_credentials_or_internals():
    config = Settings(
        database_url="postgresql+psycopg://private_user:private_password@localhost:1/private_db",
        token_pepper="test-pepper-" * 4,
        database_connect_timeout=1,
    )
    with TestClient(create_app(config)) as client:
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + "a" * 43})
        assert response.status_code == 503
        assert "private_" not in response.text
        assert "SELECT" not in response.text


def test_validation_and_unexpected_errors_are_sanitized():
    app = create_app(settings())

    @app.get("/test-validation")
    def validate(value: int = Query()):
        return value

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("database-password-secret")

    with TestClient(app) as client:
        response = client.get("/test-validation", params={"value": "submitted-secret"})
        assert response.status_code == 422
        assert "submitted-secret" not in response.text
        response = client.get("/test-failure")
        assert response.status_code == 500
        assert "database-password-secret" not in response.text


@pytest.mark.parametrize(
    "field,value", [("owner_id", str(uuid4())), ("image", "untrusted"), ("ttl_seconds", True)]
)
def test_resource_contract_rejects_owner_injection_arbitrary_image_and_boolean_ttl(field, value):
    payload = {
        "project_id": str(uuid4()),
        "display_name": "Feature database",
        "template_id": "postgres",
        "target_id": "local",
        "size_id": "small",
        field: value,
    }
    with pytest.raises(ValidationError):
        ResourceRequest.model_validate(payload)


def test_renew_contract_requires_timezone_and_public_views_omit_secrets():
    with pytest.raises(ValidationError):
        RenewRequest(expected_revision=1, expires_at=datetime(2026, 10, 31))
    now = datetime.now(UTC)
    view = ResourceView(
        id=uuid4(),
        project_id=uuid4(),
        owner_id=uuid4(),
        display_name="db",
        template_id="postgres",
        target_id="local",
        size_id="small",
        desired_state="running",
        status="pending",
        revision=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert not {"dsn", "password", "credentials", "ciphertext"} & view.model_dump().keys()


def test_config_and_token_fingerprints_do_not_expose_secrets():
    config = settings()
    assert config.token_pepper.get_secret_value() not in repr(config)
    assert config.database_url.get_secret_value() not in repr(config)
    assert token_digest("token", "pepper-one") != token_digest("token", "pepper-two")
    with pytest.raises(ValidationError) as error:
        Settings(database_url="sqlite:///secret", token_pepper="x" * 40)
    assert "sqlite:///secret" not in str(error.value)


def test_http_transport_works_with_fake_application_ports():
    now = datetime.now(UTC)
    user, project, token_id = uuid4(), uuid4(), uuid4()

    class Reader:
        def find_by_digest(self, digest):
            return CredentialSnapshot(
                token_id,
                user,
                project,
                "developer",
                ("catalog:read",),
                True,
                now + timedelta(hours=1),
                None,
            )

    class Hasher:
        def digest(self, token):
            return "synthetic-digest"

    services = ApiServices(
        Authenticate(Reader(), Hasher(), lambda: now), ReadCatalog(), lambda: "ready"
    )
    with TestClient(create_api(services)) as client:
        headers = {"Authorization": "Bearer " + "x" * 43}
        me = client.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["project_id"] == str(project)
        assert me.headers["cache-control"] == "no-store"
        catalog = client.get("/api/v1/catalog", headers=headers)
        assert catalog.json() == {
            "project_id": str(project),
            "templates": [],
            "message": "No provisioning providers are enabled in this foundation release",
        }
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/resources", headers=headers).status_code == 404
