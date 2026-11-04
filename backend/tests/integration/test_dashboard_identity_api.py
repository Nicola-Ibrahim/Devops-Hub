"""Dashboard-facing identity contracts against isolated PostgreSQL schemas."""

import pytest
from test_browser_identity_postgres import ORIGIN, PASSWORD, PEPPER, seed_user
from test_foundation_postgres import client_for

from entrypoints.settings import Settings

pytestmark = pytest.mark.postgres


def config():
    return Settings(
        database_url="postgresql+psycopg://localhost/devops_hub_test",
        token_pepper=PEPPER,
        cookie_secure=False,
        browser_allowed_origins=(ORIGIN,),
    )


def login(client, name, project_id, password=PASSWORD):
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"userName": name, "password": password, "projectId": str(project_id)},
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "no-store" in response.headers["cache-control"]
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}


def test_session_controls_password_change_and_logout_all(postgres_engine):
    _, project_id, name = seed_user(postgres_engine)
    with (
        client_for(postgres_engine, config()) as current,
        client_for(postgres_engine, config()) as other,
    ):
        headers = login(current, name, project_id)
        login(other, name, project_id)
        sessions = current.get("/api/v1/me/sessions")
        assert sessions.status_code == 200
        assert "no-store" in sessions.headers["cache-control"]
        assert len(sessions.json()) == 2
        assert sum(item["current"] for item in sessions.json()) == 1
        target = next(item["sessionId"] for item in sessions.json() if not item["current"])
        assert (
            current.delete(f"/api/v1/me/sessions/{target}", headers={"Origin": ORIGIN}).status_code
            == 422
        )
        assert (
            current.delete(
                f"/api/v1/me/sessions/{target}",
                headers={**headers, "Origin": "https://foreign.invalid"},
            ).status_code
            == 401
        )
        assert other.get("/api/v1/me/sessions").status_code == 200
        assert current.delete(f"/api/v1/me/sessions/{target}", headers=headers).status_code == 204
        assert other.get("/api/v1/me/sessions").status_code == 401
        login(other, name, project_id)
        response = current.post(
            "/api/v1/me/password",
            headers=headers,
            json={"currentPassword": PASSWORD, "newPassword": "replacement-private-test-password"},
        )
        assert response.status_code == 204
        assert current.get("/api/v1/me/sessions").status_code == 401
        assert other.get("/api/v1/me/sessions").status_code == 401
        assert (
            current.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"userName": name, "password": PASSWORD, "projectId": str(project_id)},
            ).status_code
            == 401
        )
        headers = login(current, name, project_id, "replacement-private-test-password")
        login(other, name, project_id, "replacement-private-test-password")
        assert current.post("/api/v1/auth/logout-all", headers=headers).status_code == 200
        assert other.get("/api/v1/me/sessions").status_code == 401
        assert current.get("/api/v1/me/sessions").status_code == 401


def test_membership_administration_enforces_role_project_and_admin_retention(postgres_engine):
    admin_id, project_a, admin_name = seed_user(postgres_engine)
    member_id, project_b, member_name = seed_user(postgres_engine, role="developer")
    with (
        client_for(postgres_engine, config()) as admin,
        client_for(postgres_engine, config()) as member,
    ):
        headers = login(admin, admin_name, project_a)
        route = f"/api/v1/projects/{project_a}/members"
        assert admin.get(f"/api/v1/projects/{project_b}/members").status_code == 401
        assert (
            admin.put(
                f"{route}/{member_id}", headers=headers, json={"role": "developer"}
            ).status_code
            == 204
        )
        member_headers = login(member, member_name, project_a)
        assert member.get(route).status_code == 401
        assert (
            member.put(
                f"{route}/{member_id}", headers=member_headers, json={"role": "admin"}
            ).status_code
            == 401
        )
        assert member.get("/api/v1/me/sessions").status_code == 200
        assert admin.delete(f"{route}/{admin_id}", headers=headers).status_code == 422
        assert (
            admin.put(
                f"{route}/{admin_id}", headers=headers, json={"role": "developer"}
            ).status_code
            == 422
        )
        assert (
            admin.put(f"{route}/{member_id}", headers=headers, json={"role": "admin"}).status_code
            == 204
        )
        assert member.get(route).status_code == 200
        members = admin.get(route)
        assert "no-store" in members.headers["cache-control"]
        assert {item["userId"] for item in members.json()} == {str(admin_id), str(member_id)}
        assert admin.delete(f"{route}/{member_id}", headers=headers).status_code == 204
        assert member.get(route).status_code == 401
        assert len(admin.get(route).json()) == 1
