import asyncio
from uuid import uuid4

import httpx
import pytest

from identity.application.authorization.models import AuthorizationRequest
from identity.application.authorization.port import AuthorizationUnavailable
from identity.infra.authorization.opa import OpaAuthorizationClient


def request() -> AuthorizationRequest:
    return AuthorizationRequest(
        subject_id=uuid4(),
        action="database:read",
        resource_kind="database",
        project_id=uuid4(),
        role="developer",
        scopes=("resource:read",),
    )


@pytest.mark.parametrize("allowed", [True, False])
def test_returns_opa_allow_or_deny(allowed: bool) -> None:
    seen: list[httpx.Request] = []

    def respond(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"result": {"allow": allowed, "policy_revision": "r1"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await OpaAuthorizationClient("http://opa:8181", client).evaluate(request())

    result = asyncio.run(run())

    assert result.allowed is allowed
    assert result.policy_revision == "r1"
    assert seen[0].url.path == "/v1/data/devops/identity/decision"
    assert b"database:read" in seen[0].content


@pytest.mark.parametrize("body", [{}, {"result": {}}, {"result": {"allow": "true"}}])
def test_missing_or_malformed_decision_fails_closed(body: dict[str, object]) -> None:
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as client:
            with pytest.raises(AuthorizationUnavailable):
                await OpaAuthorizationClient("http://opa:8181", client).evaluate(request())

    asyncio.run(run())


def test_transport_failure_is_sanitized() -> None:
    async def run(error_type):
        async def fail(_: httpx.Request) -> httpx.Response:
            raise error_type("sensitive endpoint detail")

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            with pytest.raises(AuthorizationUnavailable) as error:
                await OpaAuthorizationClient("http://opa:8181", client).evaluate(request())
        return error.value

    for error_type in (httpx.ConnectError, httpx.ReadTimeout):
        error = asyncio.run(run(error_type))
        assert "sensitive endpoint detail" not in str(error)
