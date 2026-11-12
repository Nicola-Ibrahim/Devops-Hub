"""HTTP adapter for the OPA decision API."""

from urllib.parse import urlsplit

import httpx

from identity.application.authorization.models import AuthorizationDecision, AuthorizationRequest
from identity.application.authorization.port import AuthorizationUnavailable


class OpaAuthorizationClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient, timeout: float = 2.0) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("OPA endpoint must be an HTTP URL")
        self._url = base_url.rstrip("/") + "/v1/data/devops/identity/decision"
        self._client = client
        self._timeout = timeout

    async def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        payload = {
            "input": {
                "subject": {
                    "id": str(request.subject_id),
                    "role": request.role,
                    "scopes": list(request.scopes),
                    "project_id": str(request.subject_project_id)
                    if request.subject_project_id
                    else None,
                },
                "action": request.action,
                "resource": {
                    "kind": request.resource_kind,
                    "id": str(request.resource_id) if request.resource_id else None,
                    "project_id": str(request.project_id) if request.project_id else None,
                    "owner_id": str(request.owner_id) if request.owner_id else None,
                },
            }
        }
        try:
            response = await self._client.post(self._url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            body = response.json()
            result = body.get("result") if isinstance(body, dict) else None
            if not isinstance(result, dict) or type(result.get("allow")) is not bool:
                raise AuthorizationUnavailable("OPA returned an invalid decision")
            revision = result.get("policy_revision")
            if revision is not None and not isinstance(revision, str):
                raise AuthorizationUnavailable("OPA returned an invalid decision")
            return AuthorizationDecision(result["allow"], revision)
        except AuthorizationUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AuthorizationUnavailable("OPA decision is unavailable") from exc
