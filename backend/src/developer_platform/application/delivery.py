"""Application generation and delivery workflows, expressed as repository/provider ports."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError

StepKind = Literal[
    "repository",
    "resource",
    "deployment",
    "template_update",
    "preview_cleanup",
]
StepStatus = Literal["pending", "running", "succeeded", "failed"]
ApplicationStatus = Literal["pending", "ready", "failed", "deleting", "deleted"]

_APP_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_DIGEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,250}@sha256:[a-f0-9]{64}\Z")
_IDEMPOTENCY = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")


def _safe_repository_name(value: str) -> bool:
    return bool(_REPOSITORY.fullmatch(value)) and ".." not in value


@dataclass(frozen=True)
class TemplateVersion:
    template_id: str
    version: str
    language: str
    display_name: str
    description: str


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class ApplicationCommand:
    environment_id: UUID
    name: str
    template_id: str
    template_version: str


@dataclass(frozen=True)
class ResourceAttachmentCommand:
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int


@dataclass(frozen=True)
class DeploymentCommand:
    image_digest: str
    target_id: str = "local"


@dataclass(frozen=True)
class ApplicationDetails:
    id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    name: str
    template_id: str
    template_version: str
    repository_url: str | None
    resource_id: UUID | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    is_preview: bool = False
    source_repository: str | None = None
    pull_request: int | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class DeliveryStepDetails:
    id: UUID
    application_id: UUID
    kind: StepKind
    status: StepStatus
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DeploymentDetails:
    id: UUID
    application_id: UUID
    image_digest: str
    target_id: str
    status: StepStatus
    url: str | None
    created_at: datetime


@dataclass(frozen=True)
class DeliveryClaim:
    step_id: UUID
    application_id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    application_name: str
    template_id: str
    template_version: str
    kind: StepKind
    idempotency_key: str
    claim_token: UUID
    attempts: int
    payload: dict[str, object]


@dataclass(frozen=True)
class DeliveryResult:
    repository_url: str | None = None
    resource_id: UUID | None = None
    deployment_id: UUID | None = None
    deployment_url: str | None = None
    provider_reference: str | None = None


@dataclass(frozen=True)
class RegisteredRepository:
    project_id: UUID
    environment_id: UUID
    canonical_repository: str


@dataclass(frozen=True)
class WebhookResult:
    accepted: bool
    duplicate: bool
    application_id: UUID | None
    cleanup_count: int = 0
    reason: str | None = None


class TemplateCatalog(Protocol):
    def list_templates(self) -> tuple[TemplateVersion, ...]: ...

    def get(self, template_id: str, version: str) -> TemplateVersion: ...

    def render(
        self, template_id: str, version: str, values: dict[str, str]
    ) -> tuple[GeneratedFile, ...]: ...


class WebhookSignatureVerifier(Protocol):
    """Verifies a provider signature and parses its authenticated JSON payload."""

    def verify(self, raw_body: bytes, signature: str | None) -> tuple[dict[str, object], str]: ...


class RequestFingerprint(Protocol):
    def for_value(self, value: object) -> str: ...


class ApplicationDeliveryRepository(Protocol):
    async def create_application(
        self,
        access: AccessContext,
        command: ApplicationCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[ApplicationDetails, bool]: ...

    async def list_applications(self, project_id: UUID) -> tuple[ApplicationDetails, ...]: ...

    async def find_application(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDetails | None: ...

    async def list_steps(self, application_id: UUID) -> tuple[DeliveryStepDetails, ...]: ...

    async def enqueue_resource_attachment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeliveryStepDetails: ...

    async def enqueue_deployment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeploymentDetails: ...

    async def deployment_history(
        self, project_id: UUID, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]: ...

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID, now: datetime
    ) -> DeliveryStepDetails: ...

    async def record_webhook(
        self,
        *,
        delivery_id: str,
        payload_hash: str,
        event: str,
        repository: str,
        pull_request: int | None,
        action: str,
        now: datetime,
    ) -> bool: ...

    async def find_registered_repository(self, repository: str) -> RegisteredRepository | None: ...

    async def request_preview(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        repository: str,
        pull_request: int,
        branch: str,
        head_sha: str,
        image_digest: str | None,
        template_id: str,
        template_version: str,
        ttl_seconds: int,
        now: datetime,
    ) -> UUID | None: ...

    async def close_preview(self, *, repository: str, pull_request: int, now: datetime) -> int: ...

    async def expire_previews(self, now: datetime, limit: int) -> int: ...

    async def claim_step(self, now: datetime, lease_seconds: int) -> DeliveryClaim | None: ...

    async def heartbeat_step(
        self, claim: DeliveryClaim, now: datetime, lease_seconds: int
    ) -> bool: ...

    async def complete_step(
        self, claim: DeliveryClaim, result: DeliveryResult, now: datetime
    ) -> bool: ...

    async def fail_step(
        self,
        claim: DeliveryClaim,
        error_code: str,
        now: datetime,
        retry_after_seconds: int,
        retryable: bool,
    ) -> bool: ...


class RepositoryProvisioner(Protocol):
    async def create_repository(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        name: str,
        template: TemplateVersion,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str: ...

    async def create_update_pull_request(
        self,
        *,
        repository_url: str,
        branch: str,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str: ...


class ResourceProvisioner(Protocol):
    async def request(
        self,
        *,
        project_id: UUID,
        environment_id: UUID,
        owner_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> UUID: ...

    async def ready(self, project_id: UUID, resource_id: UUID) -> bool: ...

    async def delete(
        self, project_id: UUID, owner_id: UUID, resource_id: UUID, idempotency_key: str
    ) -> None: ...


class ApplicationDeployer(Protocol):
    async def deploy(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        image_digest: str,
        target_id: str,
        resource_id: UUID | None,
        idempotency_key: str,
    ) -> tuple[str, str]: ...

    async def remove(
        self, project_id: UUID, application_id: UUID, idempotency_key: str
    ) -> None: ...


class ApplicationDeliveryFailure(Exception):
    def __init__(self, code: str, retryable: bool = True) -> None:
        super().__init__(code)
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code) else "delivery_failed"
        self.retryable = retryable


class ApprovedImageCatalog(Protocol):
    def is_approved(self, digest: str, target_id: str) -> bool: ...


class ApplicationDelivery:
    def __init__(
        self,
        repository: ApplicationDeliveryRepository,
        templates: TemplateCatalog,
        clock: Callable[[], datetime],
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        webhook_verifier: WebhookSignatureVerifier | None = None,
        allowed_repository_owner: str | None = None,
        preview_owner_id: UUID | None = None,
        preview_ttl_seconds: int = 14400,
    ) -> None:
        self.repository = repository
        self.templates = templates
        self.clock = clock
        self.images = images
        self.fingerprint = fingerprint
        self.webhook_verifier = webhook_verifier
        self.allowed_repository_owner = allowed_repository_owner
        self.preview_owner_id = preview_owner_id
        self.preview_ttl_seconds = preview_ttl_seconds

    def available_templates(self) -> tuple[TemplateVersion, ...]:
        return self.templates.list_templates()

    async def create_application(
        self, access: AccessContext, command: ApplicationCommand, idempotency_key: str
    ) -> tuple[ApplicationDetails, bool]:
        self._require_scope(access, "resources:write")
        self._validate_key(idempotency_key)
        if not _APP_NAME.fullmatch(command.name):
            raise PlatformRequestError(
                "invalid_application_name", "Application name is invalid", 422
            )
        if not _IDENTIFIER.fullmatch(command.template_id):
            raise PlatformRequestError("invalid_template", "Template identifier is invalid", 422)
        self.templates.get(command.template_id, command.template_version)
        payload_hash = self.fingerprint.for_value(command)
        return await self.repository.create_application(
            access, command, idempotency_key, payload_hash, self.clock()
        )

    async def list_applications(self, access: AccessContext) -> tuple[ApplicationDetails, ...]:
        if "resources:read" not in access.scopes:
            raise PlatformRequestError("forbidden", "Application access is not permitted", 403)
        return await self.repository.list_applications(access.project_id)

    async def application(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        if "resources:read" not in access.scopes:
            raise PlatformRequestError("forbidden", "Application access is not permitted", 403)
        application = await self.repository.find_application(access.project_id, application_id)
        if application is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return application, await self.repository.list_steps(application.id)

    async def attach_resource(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> DeliveryStepDetails:
        self._require_scope(access, "resources:write")
        self._validate_key(idempotency_key)
        if command.ttl_seconds < 60 or command.ttl_seconds > 86400:
            raise PlatformRequestError("invalid_lease", "Resource lifetime is outside policy", 422)
        return await self.repository.enqueue_resource_attachment(
            access,
            application_id,
            command,
            idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )

    async def deploy(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
    ) -> DeploymentDetails:
        self._require_scope(access, "resources:write")
        self._validate_key(idempotency_key)
        if not _DIGEST.fullmatch(command.image_digest):
            raise PlatformRequestError(
                "immutable_image_required",
                "Deployment requires an image pinned by SHA-256 digest",
                422,
            )
        if not self.images.is_approved(command.image_digest, command.target_id):
            raise PlatformRequestError(
                "image_not_approved", "Image is not approved for this target", 403
            )
        return await self.repository.enqueue_deployment(
            access,
            application_id,
            command,
            idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )

    async def deployment_history(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        if "resources:read" not in access.scopes:
            raise PlatformRequestError("forbidden", "Application access is not permitted", 403)
        if await self.repository.find_application(access.project_id, application_id) is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return await self.repository.deployment_history(access.project_id, application_id)

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID
    ) -> DeliveryStepDetails:
        self._require_scope(access, "resources:write")
        return await self.repository.retry_step(access, application_id, step_id, self.clock())

    async def process_github_webhook(
        self, *, raw_body: bytes, signature: str | None, delivery_id: str, event: str
    ) -> WebhookResult:
        if self.webhook_verifier is None or self.allowed_repository_owner is None:
            raise PlatformRequestError(
                "webhooks_disabled", "GitHub preview events are not configured", 503
            )
        if len(raw_body) > 1024 * 1024 or not re.fullmatch(r"[A-Fa-f0-9-]{16,100}", delivery_id):
            raise PlatformRequestError("webhook_invalid", "Webhook envelope is invalid", 400)
        payload, payload_hash = self.webhook_verifier.verify(raw_body, signature)
        action = payload.get("action")
        repository_data = payload.get("repository")
        pull_request = payload.get("pull_request")
        if (
            event != "pull_request"
            or not isinstance(action, str)
            or action not in {"opened", "reopened", "synchronize", "closed"}
            or not isinstance(repository_data, dict)
            or not isinstance(pull_request, dict)
        ):
            raise PlatformRequestError("webhook_invalid", "Unsupported GitHub event", 400)
        repository = repository_data.get("full_name")
        if not isinstance(repository, str) or not _safe_repository_name(repository):
            raise PlatformRequestError("webhook_invalid", "Repository identity is invalid", 400)
        owner, _ = repository.split("/", 1)
        if owner.casefold() != self.allowed_repository_owner.casefold():
            raise PlatformRequestError("webhook_forbidden", "Repository is not approved", 403)
        number = pull_request.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise PlatformRequestError("webhook_invalid", "Pull request identity is invalid", 400)
        recorded = await self.repository.record_webhook(
            delivery_id=delivery_id,
            payload_hash=payload_hash,
            event=event,
            repository=repository.casefold(),
            pull_request=number,
            action=action,
            now=self.clock(),
        )
        if not recorded:
            return WebhookResult(True, True, None, reason="duplicate_delivery")
        registered = await self.repository.find_registered_repository(repository.casefold())
        if registered is None:
            return WebhookResult(False, False, None, reason="repository_not_registered")
        if action == "closed":
            count = await self.repository.close_preview(
                repository=repository.casefold(), pull_request=number, now=self.clock()
            )
            return WebhookResult(True, False, None, cleanup_count=count)
        head = pull_request.get("head")
        base = pull_request.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            return WebhookResult(False, False, None, reason="pull_request_head_missing")
        head_repo = head.get("repo")
        base_repo = base.get("repo")
        if not isinstance(head_repo, dict) or not isinstance(base_repo, dict):
            return WebhookResult(False, False, None, reason="pull_request_repo_missing")
        head_full_name, base_full_name = head_repo.get("full_name"), base_repo.get("full_name")
        if (
            not isinstance(head_full_name, str)
            or head_full_name.casefold() != repository.casefold()
        ):
            return WebhookResult(False, False, None, reason="untrusted_fork")
        if (
            not isinstance(base_full_name, str)
            or base_full_name.casefold() != repository.casefold()
        ):
            return WebhookResult(False, False, None, reason="pull_request_base_mismatch")
        if self.preview_owner_id is None:
            return WebhookResult(False, False, None, reason="preview_owner_not_configured")
        head_sha, branch = head.get("sha"), head.get("ref")
        if (
            not isinstance(head_sha, str)
            or not re.fullmatch(r"[a-f0-9]{40}", head_sha)
            or not isinstance(branch, str)
            or len(branch) > 255
            or ".." in branch
        ):
            return WebhookResult(False, False, None, reason="untrusted_head_reference")
        image_digest = pull_request.get("platform_image_digest")
        if image_digest is not None and (
            not isinstance(image_digest, str)
            or not _DIGEST.fullmatch(image_digest)
            or not self.images.is_approved(image_digest, "local")
        ):
            return WebhookResult(False, False, None, reason="preview_image_not_approved")
        application_id = await self.repository.request_preview(
            project_id=registered.project_id,
            owner_id=self.preview_owner_id,
            repository=repository.casefold(),
            pull_request=number,
            branch=branch,
            head_sha=head_sha,
            image_digest=image_digest,
            template_id="python-fastapi",
            template_version="1.0.0",
            ttl_seconds=self.preview_ttl_seconds,
            now=self.clock(),
        )
        return WebhookResult(True, False, application_id)

    async def execute_claim(
        self,
        claim: DeliveryClaim,
        repositories: RepositoryProvisioner | None,
        resources: ResourceProvisioner | None,
        deployer: ApplicationDeployer | None,
    ) -> DeliveryResult:
        if claim.kind == "repository":
            if repositories is None:
                raise ApplicationDeliveryFailure("repository_provider_disabled")
            template = self.templates.get(claim.template_id, claim.template_version)
            files = self.templates.render(
                claim.template_id,
                claim.template_version,
                {"application_name": claim.application_name},
            )
            url = await repositories.create_repository(
                project_id=claim.project_id,
                application_id=claim.application_id,
                name=claim.application_name,
                template=template,
                files=files,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(repository_url=url)
        if claim.kind == "resource":
            if resources is None:
                raise ApplicationDeliveryFailure("resource_provider_disabled")
            ttl_raw = claim.payload.get("ttl_seconds", 0)
            if not isinstance(ttl_raw, int) or isinstance(ttl_raw, bool):
                raise ApplicationDeliveryFailure("resource_request_invalid", retryable=False)
            command = ResourceAttachmentCommand(
                template_id=str(claim.payload.get("template_id", "")),
                version=str(claim.payload.get("version", "")),
                target_id=str(claim.payload.get("target_id", "")),
                size_id=str(claim.payload.get("size_id", "")),
                ttl_seconds=ttl_raw,
            )
            resource_id = await resources.request(
                project_id=claim.project_id,
                environment_id=claim.environment_id,
                owner_id=claim.owner_id,
                command=command,
                idempotency_key=claim.idempotency_key,
            )
            # Persist the stable resource ID before readiness polling. The SQL worker
            # adapter retries this same idempotent request until the owned row is ready;
            # close/expiry can then always enqueue cleanup with the known ID.
            return DeliveryResult(resource_id=resource_id)
        if claim.kind == "deployment":
            if deployer is None:
                raise ApplicationDeliveryFailure("deployment_target_disabled")
            image_digest = str(claim.payload.get("image_digest", ""))
            target_id = str(claim.payload.get("target_id", "local"))
            if not self.images.is_approved(image_digest, target_id):
                raise ApplicationDeliveryFailure("image_not_approved", retryable=False)
            deployment_id = UUID(str(claim.payload["deployment_id"]))
            resource_id_raw = claim.payload.get("resource_id")
            deployment_resource_id = UUID(str(resource_id_raw)) if resource_id_raw else None
            url, reference = await deployer.deploy(
                project_id=claim.project_id,
                application_id=claim.application_id,
                deployment_id=deployment_id,
                image_digest=image_digest,
                target_id=target_id,
                resource_id=deployment_resource_id,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(
                deployment_id=deployment_id,
                deployment_url=url,
                provider_reference=reference,
            )
        if claim.kind == "template_update":
            if repositories is None:
                raise ApplicationDeliveryFailure("repository_provider_disabled")
            repository_url = str(claim.payload.get("repository_url", ""))
            files = self.templates.render(
                claim.template_id,
                claim.template_version,
                {"application_name": claim.application_name},
            )
            pull_request_url = await repositories.create_update_pull_request(
                repository_url=repository_url,
                branch=f"platform/template-{claim.template_version}",
                files=files,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(provider_reference=pull_request_url)
        if claim.kind == "preview_cleanup":
            if claim.payload.get("remove_deployments") is True:
                if deployer is None:
                    raise ApplicationDeliveryFailure("deployment_target_disabled")
                await deployer.remove(claim.project_id, claim.application_id, claim.idempotency_key)
            cleanup_resource_id = claim.payload.get("resource_id")
            if cleanup_resource_id is not None:
                if resources is None:
                    raise ApplicationDeliveryFailure("resource_provider_disabled")
                await resources.delete(
                    claim.project_id,
                    claim.owner_id,
                    UUID(str(cleanup_resource_id)),
                    claim.idempotency_key + ":resource",
                )
            return DeliveryResult()
        raise ApplicationDeliveryFailure("unknown_delivery_step", retryable=False)

    @staticmethod
    def _require_scope(access: AccessContext, scope: str) -> None:
        if access.project_id is None or scope not in access.scopes:
            raise PlatformRequestError("forbidden", "Application access is not permitted", 403)

    @staticmethod
    def _validate_key(value: str) -> None:
        if not _IDEMPOTENCY.fullmatch(value):
            raise PlatformRequestError("invalid_idempotency_key", "Idempotency-Key is invalid", 422)
