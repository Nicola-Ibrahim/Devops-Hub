"""Application boundary for policy evaluation."""

from typing import Protocol

from identity.application.authorization.models import AuthorizationDecision, AuthorizationRequest


class AuthorizationUnavailable(Exception):
    """Policy decision could not be obtained or validated."""


class AuthorizationDecisionPort(Protocol):
    async def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision: ...
