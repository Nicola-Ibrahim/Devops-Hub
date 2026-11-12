"""API boundary helper for enforcing Identity policies before dispatch."""

import logging
from uuid import UUID

from api.errors import APIError
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.authorization.models import AuthorizationRequest
from identity.application.authorization.port import (
    AuthorizationDecisionPort,
    AuthorizationUnavailable,
)
from identity.application.module import IdentityModule

logger = logging.getLogger(__name__)


async def require_identity_permission(
    *,
    module: IdentityModule,
    authorizer: AuthorizationDecisionPort,
    session_token: str,
    action: str,
    resource_kind: str,
    resource_id: UUID | None = None,
    project_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> None:
    principal = await module.query(AuthenticateSessionQuery(session_token, project_id))
    request = AuthorizationRequest(
        subject_id=principal.user_id,
        action=action,
        resource_kind=resource_kind,
        resource_id=resource_id,
        project_id=project_id,
        subject_project_id=principal.project_id,
        role=principal.role,
        scopes=tuple(principal.scopes),
        owner_id=owner_id or principal.user_id,
    )
    try:
        decision = await authorizer.evaluate(request)
    except AuthorizationUnavailable:
        logger.warning("identity_policy action=%s outcome=unavailable", action)
        raise APIError(
            503, "authorization_unavailable", "Authorization is temporarily unavailable"
        ) from None
    logger.info(
        "identity_policy subject=%s action=%s project=%s allowed=%s revision=%s",
        principal.user_id,
        action,
        project_id,
        decision.allowed,
        decision.policy_revision,
    )
    if not decision.allowed:
        raise APIError(403, "forbidden", "Permission denied")
