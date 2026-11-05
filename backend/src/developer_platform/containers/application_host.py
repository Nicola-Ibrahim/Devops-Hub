"""Outer transaction boundary and durable worker for application delivery."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.credentials import RequestIdentity
from developer_platform.application.delivery import (
    ApplicationCommand,
    ApplicationDelivery,
    ApplicationDeliveryFailure,
    ApplicationDeliveryRepository,
    ApplicationDeployer,
    ApplicationDetails,
    ApprovedImageCatalog,
    DeliveryClaim,
    DeliveryResult,
    DeliveryStepDetails,
    DeploymentCommand,
    DeploymentDetails,
    RepositoryProvisioner,
    RequestFingerprint,
    ResourceAttachmentCommand,
    ResourceProvisioner,
    TemplateCatalog,
    TemplateVersion,
    WebhookResult,
    WebhookSignatureVerifier,
)
from developer_platform.application.delivery_effects import ExecuteDeliveryStep
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.infra.persistence.delivery import SQLAlchemyApplicationDeliveryRepository
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork

T = TypeVar("T")
R = TypeVar("R")
Clock = Callable[[], datetime]
AuthenticateRequest = Callable[[AsyncSession, RequestIdentity], Awaitable[AccessContext]]


class ApplicationDeliveryHost:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        authenticate: AuthenticateRequest,
        templates: TemplateCatalog,
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        webhook_verifier: WebhookSignatureVerifier | None = None,
        repositories: RepositoryProvisioner | None = None,
        resources: ResourceProvisioner | None = None,
        deployer: ApplicationDeployer | None = None,
        allowed_repository_owner: str | None = None,
        preview_owner_id: UUID | None = None,
        preview_ttl_seconds: int = 14400,
        *,
        effect_guard: Callable[[UUID], AbstractAsyncContextManager[bool]],
    ) -> None:
        self.effect_guard = effect_guard
        self.sessions = sessions
        self.clock = clock
        self.authenticate = authenticate
        self.template_catalog = templates
        self.images = images
        self.fingerprint = fingerprint
        self.webhook_verifier = webhook_verifier
        self.repositories = repositories
        self.resources = resources
        self.deployer = deployer
        self.allowed_repository_owner = allowed_repository_owner
        self.preview_owner_id = preview_owner_id
        self.preview_ttl_seconds = preview_ttl_seconds

    def templates(self) -> tuple[TemplateVersion, ...]:
        return self.template_catalog.list_templates()

    async def _run(
        self,
        identity: RequestIdentity,
        action: Callable[[ApplicationDelivery, AccessContext], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        try:
            async with self.sessions() as session:
                unit = SqlAlchemyUnitOfWork(session)
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                delivery = self._use_case(repository)

                async def authorized() -> T:
                    access = await self.authenticate(session, identity)
                    return await action(delivery, access)

                return await unit.run(authorized, present)
        except DatabaseUnavailable as error:
            raise PlatformRequestError(
                "delivery_unavailable", "Application delivery database is unavailable", 503
            ) from error

    async def create_application(
        self, identity: RequestIdentity, command: ApplicationCommand, key: str
    ) -> tuple[ApplicationDetails, bool]:
        return await self._run(
            identity,
            lambda usecase, access: usecase.create_application(access, command, key),
            lambda result: result,
        )

    async def list_applications(self, identity: RequestIdentity) -> tuple[ApplicationDetails, ...]:
        return await self._run(
            identity,
            lambda usecase, access: usecase.list_applications(access),
            tuple,
        )

    async def application(
        self, identity: RequestIdentity, application_id: UUID
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        return await self._run(
            identity,
            lambda usecase, access: usecase.application(access, application_id),
            lambda result: result,
        )

    async def attach_resource(
        self,
        identity: RequestIdentity,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        key: str,
    ) -> DeliveryStepDetails:
        return await self._run(
            identity,
            lambda usecase, access: usecase.attach_resource(access, application_id, command, key),
            lambda result: result,
        )

    async def deploy(
        self,
        identity: RequestIdentity,
        application_id: UUID,
        command: DeploymentCommand,
        key: str,
    ) -> DeploymentDetails:
        return await self._run(
            identity,
            lambda usecase, access: usecase.deploy(access, application_id, command, key),
            lambda result: result,
        )

    async def deployment_history(
        self, identity: RequestIdentity, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        return await self._run(
            identity,
            lambda usecase, access: usecase.deployment_history(access, application_id),
            tuple,
        )

    async def retry_step(
        self, identity: RequestIdentity, application_id: UUID, step_id: UUID
    ) -> DeliveryStepDetails:
        return await self._run(
            identity,
            lambda usecase, access: usecase.retry_step(access, application_id, step_id),
            lambda result: result,
        )

    async def github_webhook(
        self, raw_body: bytes, signature: str | None, delivery_id: str | None, event: str | None
    ) -> WebhookResult:
        if delivery_id is None or event is None:
            raise PlatformRequestError(
                "webhook_invalid", "GitHub delivery headers are required", 400
            )
        try:
            async with self.sessions() as session:
                unit = SqlAlchemyUnitOfWork(session)
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                usecase = self._use_case(repository)
                return await unit.run(
                    lambda: usecase.process_github_webhook(
                        raw_body=raw_body,
                        signature=signature,
                        delivery_id=delivery_id,
                        event=event,
                    ),
                    lambda result: result,
                )
        except DatabaseUnavailable as error:
            raise PlatformRequestError(
                "delivery_unavailable", "Application delivery database is unavailable", 503
            ) from error

    async def tick(self) -> bool:
        now = self.clock()
        claim = await self._worker_transaction(
            lambda repo: self._claim(repo, now), lambda result: result
        )
        if claim is None:
            return False
        heartbeat = asyncio.create_task(self._heartbeat(claim))
        try:
            async with self.effect_guard(claim.application_id) as acquired:
                if not acquired:
                    await self._record_failure(claim, "application_busy", True)
                    return True
                current = await self._worker_transaction(
                    lambda repo: repo.effect_is_current(claim, self.clock()), bool
                )
                if not current:
                    return True
                # Keep ownership through completion writes, so another deployment
                # cannot remove this effect while its result is still uncertain.
                await self._execute_and_complete(claim)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        return True

    async def _execute_and_complete(self, claim: DeliveryClaim) -> None:
        try:
            result = await self._effect_executor().execute(claim)
        except ApplicationDeliveryFailure as error:
            await self._record_failure(claim, error.code, error.retryable)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._record_failure(claim, "delivery_provider_failure", True)
        else:
            await self._record_success(claim, result)

    async def _claim(
        self, repository: SQLAlchemyApplicationDeliveryRepository, now: datetime
    ) -> DeliveryClaim | None:
        await repository.expire_previews(now, 100)
        return await repository.claim_step(now, 30)

    async def _heartbeat(self, claim: DeliveryClaim) -> None:
        while True:
            await asyncio.sleep(8)
            alive = await self._worker_transaction(
                lambda repo: repo.heartbeat_step(claim, self.clock(), 30), bool
            )
            if not alive:
                return

    async def _record_success(self, claim: DeliveryClaim, result: DeliveryResult) -> None:
        await self._worker_transaction(
            lambda repo: repo.complete_step(claim, result, self.clock()), bool
        )

    async def _record_failure(self, claim: DeliveryClaim, code: str, retryable: bool) -> None:
        backoff = min(300, 2 ** min(claim.attempts, 8))
        await self._worker_transaction(
            lambda repo: repo.fail_step(claim, code, self.clock(), backoff, retryable),
            bool,
        )

    async def _worker_transaction(
        self,
        action: Callable[[SQLAlchemyApplicationDeliveryRepository], Awaitable[T]],
        present: Callable[[T], R],
    ) -> R:
        try:
            async with self.sessions() as session:
                repository = SQLAlchemyApplicationDeliveryRepository(session)
                return await SqlAlchemyUnitOfWork(session).run(lambda: action(repository), present)
        except DatabaseUnavailable as error:
            raise PlatformRequestError(
                "delivery_unavailable", "Application delivery database is unavailable", 503
            ) from error

    def _use_case(self, repository: ApplicationDeliveryRepository) -> ApplicationDelivery:
        return ApplicationDelivery(
            repository,
            self.template_catalog,
            self.clock,
            self.images,
            fingerprint=self.fingerprint,
            webhook_verifier=self.webhook_verifier,
            allowed_repository_owner=self.allowed_repository_owner,
            preview_owner_id=self.preview_owner_id,
            preview_ttl_seconds=self.preview_ttl_seconds,
        )

    def _effect_executor(self) -> ExecuteDeliveryStep:
        return ExecuteDeliveryStep(
            self.template_catalog,
            self.images,
            self.repositories,
            self.resources,
            self.deployer,
        )


async def run_application_worker(
    service: ApplicationDeliveryHost, *, once: bool = False, poll_seconds: float = 1
) -> None:
    while True:
        worked = await service.tick()
        if once:
            return
        if not worked:
            await asyncio.sleep(poll_seconds)
