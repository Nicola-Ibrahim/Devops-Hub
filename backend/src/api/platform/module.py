"""HTTP host: authenticate and complete each platform dispatch transaction."""

from collections.abc import Awaitable, Callable
from dataclasses import is_dataclass, replace
from typing import Any, Literal, TypeVar, cast

from dishka import AsyncContainer
from fastapi import Request

from api.composition.platform_access import authenticate_platform_access
from api.core.security.request_identity import BrowserRequestCredentials, RequestIdentity
from devops_hub.platform.application.database_provisioning.read_resources.query import ReadProjects
from devops_hub.platform.application.module import DeveloperPlatformModule
from devops_hub.platform.application.shared.dto import AccessContext
from devops_hub.platform.application.shared.errors import PlatformRequestError, ledger_unavailable
from devops_hub.platform.application.workload_delivery.attach_database.command import AttachDatabase
from devops_hub.platform.application.workload_delivery.create_workload.command import (
    CreateApplication,
)
from devops_hub.platform.application.workload_delivery.deploy_workload.command import (
    DeployApplication,
)
from devops_hub.platform.application.workload_delivery.handle_preview_webhook.command import (
    ProcessGithubPreviewWebhook,
)
from devops_hub.platform.application.workload_delivery.read_templates.query import ReadTemplates
from devops_hub.platform.application.workload_delivery.read_workloads.query import (
    ReadApplication,
    ReadApplications,
    ReadDeploymentHistory,
)
from devops_hub.platform.application.workload_delivery.retry_delivery_step.command import (
    RetryDeliveryStep,
)
from devops_hub.platform.authorization import ALL_SCOPES, authorize_platform_action
from devops_hub.platform.infra.composition.module import DeveloperPlatformModuleDispatcher
from identity.infra.hosts.identity_sessions import authenticate_browser_operation
from shared.dispatch import Command, Query
from shared.infra.clock import Clock
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork
from shared.infra.settings import Settings

ResultT = TypeVar("ResultT")
MessageT = TypeVar("MessageT", Command[Any], Query[Any])

_DELIVERY_MESSAGES = (
    CreateApplication,
    AttachDatabase,
    DeployApplication,
    RetryDeliveryStep,
    ReadApplications,
    ReadApplication,
    ReadDeploymentHistory,
    ProcessGithubPreviewWebhook,
)


class PlatformRequestModule(DeveloperPlatformModule):
    """HTTP boundary that revalidates credentials and authorizes in one transaction."""

    def __init__(
        self, container: AsyncContainer, request: Request, settings: Settings, clock: Clock
    ) -> None:
        self._container = container
        self._request = request
        self._settings = settings
        self._clock = clock
        self._inner = DeveloperPlatformModuleDispatcher(container.get)

    async def execute(self, command: Command[ResultT]) -> ResultT:
        if isinstance(command, ProcessGithubPreviewWebhook):
            return await self._run_unscoped(command, self._inner.execute)
        return await self._run_authorized(command, self._inner.execute)

    async def query(self, query: Query[ResultT]) -> ResultT:
        if isinstance(query, ReadTemplates):
            authorize_platform_action(query)
            return cast(ResultT, await self._inner.query(query))
        return await self._run_authorized(query, self._inner.query)

    async def _run_unscoped(
        self, message: MessageT, dispatch: Callable[[MessageT], Awaitable[ResultT]]
    ) -> ResultT:
        authorize_platform_action(message)
        unit = await self._container.get(SqlAlchemyUnitOfWork)
        try:
            return await unit.run(lambda: dispatch(message), lambda result: result)
        except DatabaseUnavailable as error:
            raise self._unavailable(message) from error

    async def _run_authorized(
        self, message: MessageT, dispatch: Callable[[MessageT], Awaitable[ResultT]]
    ) -> ResultT:
        if not is_dataclass(message) or not (
            hasattr(message, "access") or isinstance(message, ReadProjects)
        ):
            raise TypeError("Platform message lacks access context")
        token: RequestIdentity = getattr(self._request.state, "request_identity", None)
        unit = await self._container.get(SqlAlchemyUnitOfWork)

        async def authorized() -> ResultT:
            if isinstance(message, ReadProjects) and isinstance(token, BrowserRequestCredentials):
                principal = await authenticate_browser_operation(
                    unit.session,
                    token.session_token,
                    None,
                    self._clock,
                    token_pepper=self._settings.token_pepper.get_secret_value(),
                )
                accesses = tuple(
                    AccessContext(
                        principal.user_id,
                        member.project_id,
                        cast(Literal["developer", "admin"], member.role),
                        frozenset(ALL_SCOPES),
                    )
                    for member in principal.memberships
                )
                current = cast(MessageT, replace(message, accesses=accesses))
            else:
                access = await authenticate_platform_access(
                    unit.session, token, self._settings, self._clock
                )
                if isinstance(message, ReadProjects):
                    current = cast(MessageT, replace(message, accesses=(access,)))
                else:
                    current = cast(MessageT, replace(message, access=access))
            authorize_platform_action(current)
            return await dispatch(current)

        try:
            return await unit.run(authorized, lambda result: result)
        except DatabaseUnavailable as error:
            raise self._unavailable(message) from error

    @staticmethod
    def _unavailable(message: object) -> PlatformRequestError:
        if isinstance(message, _DELIVERY_MESSAGES):
            return PlatformRequestError(
                "delivery_unavailable", "Application delivery database is unavailable", 503
            )
        return ledger_unavailable()
