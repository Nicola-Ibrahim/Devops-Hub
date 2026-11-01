import stat
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import migration_config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bootstrap.composition import build_services
from bootstrap.http import create_app
from bootstrap.schema import registered_metadata
from bootstrap.settings import SCHEMA_REVISION, Settings
from developer_platform.infra.persistence.models import Resource
from identity.application.dto import IssueTokenCommand
from identity.application.errors import CredentialDeliveryError
from identity.infra.credential_file import PrivateCredentialFile
from identity.infra.persistence.models import ApiToken, Membership, User
from shared.infra.persistence.audit import AuditEvent

pytestmark = pytest.mark.postgres
PEPPER = "test-only-token-pepper-" * 3


def settings():
    return Settings(
        database_url="postgresql+psycopg://localhost/devops_hub_test", token_pepper=PEPPER
    )


def client_for(engine):
    return TestClient(create_app(settings(), engine=engine))


def issue(engine, path, user="developer", project="project", **kwargs):
    token_id = build_services(settings(), engine).issue_token.execute(
        IssueTokenCommand(user_name=user, project_name=project, **kwargs),
        PrivateCredentialFile(path),
    )
    return token_id, path.read_text().strip()


def test_migrations_roundtrip_and_metadata_match(postgres_engine):
    with postgres_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
        assert compare_metadata(MigrationContext.configure(connection), registered_metadata()) == []
        command.downgrade(migration_config(connection), "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        command.upgrade(migration_config(connection), "head")
        assert compare_metadata(MigrationContext.configure(connection), registered_metadata()) == []


def test_issue_authenticate_and_revoke(postgres_engine, tmp_path, capsys):
    token_id, token = issue(postgres_engine, tmp_path / "credential")
    assert stat.S_IMODE((tmp_path / "credential").stat().st_mode) == 0o600
    with Session(postgres_engine) as session:
        record = session.get(ApiToken, token_id)
        assert record.digest != token
        assert token not in record.digest
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1
    with client_for(postgres_engine) as client:
        assert client.get("/health/ready").status_code == 200
        headers = {"Authorization": "Bearer " + token}
        me = client.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        catalog = client.get("/api/v1/catalog", headers=headers)
        assert catalog.json()["templates"] == []
        assert token not in me.text + catalog.text
        assert build_services(settings(), postgres_engine).revoke_token.execute(token_id)
        assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert token not in capsys.readouterr().out


@pytest.mark.parametrize("change", ["expired", "disabled", "membership_removed", "wrong_token"])
def test_invalid_identity_and_membership_are_denied(postgres_engine, tmp_path, change):
    token_id, token = issue(postgres_engine, tmp_path / "credential")
    with Session(postgres_engine) as session, session.begin():
        record = session.get(ApiToken, token_id)
        if change == "expired":
            record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif change == "disabled":
            session.get(User, record.user_id).active = False
        elif change == "membership_removed":
            session.delete(session.get(Membership, (record.user_id, record.project_id)))
        else:
            token = "wrong-" + token
    with client_for(postgres_engine) as client:
        assert (
            client.get("/api/v1/me", headers={"Authorization": "Bearer " + token}).status_code
            == 401
        )


def test_project_bound_principals_and_scope_enforcement(postgres_engine, tmp_path):
    _, first = issue(postgres_engine, tmp_path / "one", user="one", project="one")
    _, second = issue(
        postgres_engine, tmp_path / "two", user="two", project="two", scopes=("resources:read",)
    )
    with client_for(postgres_engine) as client:
        one = client.get("/api/v1/me", headers={"Authorization": "Bearer " + first}).json()
        two = client.get("/api/v1/me", headers={"Authorization": "Bearer " + second}).json()
        assert one["project_id"] != two["project_id"]
        assert (
            client.get("/api/v1/catalog", headers={"Authorization": "Bearer " + second}).status_code
            == 403
        )


def test_existing_output_does_not_get_overwritten_or_commit_identity(postgres_engine, tmp_path):
    output = tmp_path / "existing"
    output.write_text("original")
    with pytest.raises(CredentialDeliveryError):
        issue(postgres_engine, output, user="new", project="new")
    assert output.read_text() == "original"
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(ApiToken)) == 0


def test_failed_commit_removes_new_token_file(postgres_engine, tmp_path):
    def fail_commit(session):
        raise RuntimeError("simulated commit failure")

    output = tmp_path / "credential"
    event.listen(postgres_engine, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError):
            issue(postgres_engine, output, user="new", project="new")
    finally:
        event.remove(postgres_engine, "commit", fail_commit)
    assert not output.exists()
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(ApiToken)) == 0


def test_readiness_requires_expected_migration(postgres_engine):
    with postgres_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'unexpected'"))
    with client_for(postgres_engine) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["code"] == "schema_not_ready"


def test_database_enforces_resource_state_and_lease(postgres_engine, tmp_path):
    token_id, _ = issue(postgres_engine, tmp_path / "credential")
    with Session(postgres_engine) as session:
        token = session.get(ApiToken, token_id)
        user_id, project_id = token.user_id, token.project_id
    with Session(postgres_engine) as session, pytest.raises(IntegrityError), session.begin():
        session.add(
            Resource(
                owner_id=user_id,
                project_id=project_id,
                display_name="db",
                template_id="postgres",
                target_id="local",
                size_id="small",
                configuration={},
                installation_id=uuid4(),
                status="invented",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )


def test_pre_refactor_token_digest_still_authenticates(postgres_engine, tmp_path):
    token_id, _ = issue(postgres_engine, tmp_path / "credential")
    # Captured from the old implementation using synthetic values before the move.
    legacy_token = "synthetic-existing-token-32-characters"
    legacy_pepper = "synthetic-fixed-pepper-32-characters"
    legacy_digest = "c61fc8cd60f22172e5a3dacc20bb3c56c23ce79b1b6cf8fc8f7f20a99e582d66"
    with Session(postgres_engine) as session, session.begin():
        session.get(ApiToken, token_id).digest = legacy_digest
    config = Settings(
        database_url="postgresql+psycopg://localhost/devops_hub_test", token_pepper=legacy_pepper
    )
    with TestClient(create_app(config, engine=postgres_engine)) as client:
        assert (
            client.get(
                "/api/v1/me", headers={"Authorization": "Bearer " + legacy_token}
            ).status_code
            == 200
        )


def test_disabled_issuance_rolls_back_new_membership_and_project(postgres_engine, tmp_path):
    token_id, _ = issue(postgres_engine, tmp_path / "credential")
    from identity.domain.errors import IdentityValidationError
    from identity.infra.persistence.models import Project

    with Session(postgres_engine) as session, session.begin():
        session.get(User, session.get(ApiToken, token_id).user_id).active = False
    with pytest.raises(IdentityValidationError):
        issue(postgres_engine, tmp_path / "second", project="second")
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 1
        assert session.scalar(select(func.count()).select_from(Membership)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1
    assert not (tmp_path / "second").exists()


def test_revoke_is_idempotent_and_does_not_duplicate_audit(postgres_engine, tmp_path):
    token_id, _ = issue(postgres_engine, tmp_path / "credential")
    services = build_services(settings(), postgres_engine)
    assert services.revoke_token.execute(token_id)
    assert services.revoke_token.execute(token_id)
    assert not services.revoke_token.execute(uuid4())
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
