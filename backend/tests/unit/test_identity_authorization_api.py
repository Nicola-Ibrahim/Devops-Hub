"""Policy decisions must be enforced before Identity mutations are dispatched."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient

from api.app import create_app
from api.settings.config import BrowserCookiePolicy
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.authorization.models import AuthorizationDecision
from identity.application.authorization.port import (
    AuthorizationDecisionPort,
    AuthorizationUnavailable,
)
from identity.application.login.command import LoginCommand
from identity.application.login.result import LoginResult
from identity.application.logout.command import LogoutCommand
from identity.application.module import IdentityModule
from identity.domain.records import SessionPrincipal

USER, PROJECT, SESSION = uuid4(), uuid4(), uuid4()


class Identity:
    def __init__(self):
        self.commands = []
        self.queries = []

    async def query(self, query):
        self.queries.append(query)
        assert isinstance(query, AuthenticateSessionQuery)
        return SessionPrincipal(
            USER, "alice", SESSION, query.project_id, "project", "admin", (), (), "csrf"
        )

    async def execute(self, command):
        self.commands.append(command)
        if isinstance(command, LogoutCommand):
            return None
        assert isinstance(command, LoginCommand)
        principal = SessionPrincipal(USER, "alice", SESSION, None, None, None, (), (), "csrf")
        return LoginResult(
            "private-session", "csrf", principal, datetime.now(UTC) + timedelta(hours=8)
        )


class Policy:
    def __init__(self, unavailable=False, allowed=False):
        self.calls = []
        self.unavailable = unavailable
        self.allowed = allowed

    async def evaluate(self, request):
        self.calls.append(request)
        if self.unavailable:
            raise AuthorizationUnavailable()
        return AuthorizationDecision(self.allowed, "identity-v1")


class Bindings(Provider):
    def __init__(self, identity, policy):
        super().__init__()
        self.identity = identity
        self.policy = policy

    @provide(scope=Scope.REQUEST)
    def module(self) -> IdentityModule:
        return self.identity

    @provide(scope=Scope.REQUEST)
    def authorizer(self) -> AuthorizationDecisionPort:
        return self.policy

    @provide(scope=Scope.APP)
    def cookies(self) -> BrowserCookiePolicy:
        return BrowserCookiePolicy(False)


CASES = [
    ("GET", "/api/v1/me/browser", None, "identity.sessions.read"),
    ("GET", "/api/v1/me/sessions", None, "identity.sessions.read"),
    ("DELETE", f"/api/v1/me/sessions/{SESSION}", None, "identity.sessions.revoke"),
    ("POST", "/api/v1/auth/logout", None, "identity.logout"),
    ("POST", "/api/v1/auth/logout-all", None, "identity.logout_all"),
    ("POST", "/api/v1/auth/project", {"projectId": str(PROJECT)}, "identity.project.select"),
    (
        "POST",
        "/api/v1/me/password",
        {"currentPassword": "old-password", "newPassword": "new-password-value"},
        "identity.password.change",
    ),
    ("GET", f"/api/v1/projects/{PROJECT}/members", None, "identity.members.read"),
    (
        "PUT",
        f"/api/v1/projects/{PROJECT}/members/{USER}",
        {"role": "developer"},
        "identity.members.write",
    ),
    ("DELETE", f"/api/v1/projects/{PROJECT}/members/{USER}", None, "identity.members.write"),
]


@pytest.mark.parametrize("method,path,body,action", CASES)
@pytest.mark.parametrize("unavailable", [False, True])
def test_policy_denial_blocks_every_protected_identity_action(
    method, path, body, action, unavailable
):
    identity, policy = Identity(), Policy(unavailable)
    container = make_async_container(Bindings(identity, policy), FastapiProvider())
    try:
        with TestClient(create_app(container=container)) as client:
            client.cookies.set("devops_session", "private-session")
            response = client.request(method, path, json=body, headers={"X-CSRF-Token": "csrf"})
        assert response.status_code == (503 if unavailable else 403)
        assert not identity.commands
        assert len(identity.queries) == 1
        assert len(policy.calls) == 1
        assert policy.calls[0].action == action
        assert policy.calls[0].subject_id == USER
        if "/projects/" in path or path == "/api/v1/auth/project":
            assert identity.queries[0].project_id == PROJECT
            assert policy.calls[0].subject_project_id == PROJECT
        assert "private-session" not in response.text
    finally:
        asyncio.run(container.close())


def test_login_is_available_when_policy_service_is_unavailable():
    identity, policy = Identity(), Policy(True)
    container = make_async_container(Bindings(identity, policy), FastapiProvider())
    try:
        with TestClient(create_app(container=container)) as client:
            response = client.post(
                "/api/v1/auth/login", json={"userName": "alice", "password": "password"}
            )
        assert response.status_code == 200
        assert len(identity.commands) == 1
        assert not policy.calls
        assert "HttpOnly" in response.headers["set-cookie"]
    finally:
        asyncio.run(container.close())


def test_allowed_logout_dispatches_after_policy_check():
    identity, policy = Identity(), Policy(allowed=True)
    container = make_async_container(Bindings(identity, policy), FastapiProvider())
    try:
        with TestClient(create_app(container=container)) as client:
            client.cookies.set("devops_session", "private-session")
            response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "csrf"})
        assert response.status_code == 204
        assert len(identity.commands) == 1
        assert isinstance(identity.commands[0], LogoutCommand)
        assert len(policy.calls) == 1
    finally:
        asyncio.run(container.close())


@pytest.mark.parametrize("unavailable,expected", [(False, 200), (True, 503)])
def test_authorization_readiness_checks_policy_without_login(unavailable, expected):
    identity, policy = Identity(), Policy(unavailable)
    container = make_async_container(Bindings(identity, policy), FastapiProvider())
    try:
        with TestClient(create_app(container=container)) as client:
            response = client.get("/health/authorization")
        assert response.status_code == expected
        assert not identity.queries
        assert len(policy.calls) == 1
    finally:
        asyncio.run(container.close())
