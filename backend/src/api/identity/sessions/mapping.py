"""API response mapping for authenticated Identity principals."""

from identity.domain.records import SessionPrincipal


def _principal(principal: SessionPrincipal) -> dict[str, object]:
    return {
        "userId": str(principal.user_id),
        "userName": principal.user_name,
        "sessionId": str(principal.session_id),
        "projectId": str(principal.project_id) if principal.project_id else None,
        "projectName": principal.project_name,
        "role": principal.role,
        "scopes": list(principal.scopes),
        "csrfToken": principal.csrf_token,
        "memberships": [
            {
                "projectId": str(member.project_id),
                "projectName": member.project_name,
                "role": member.role,
            }
            for member in principal.memberships
        ],
    }
