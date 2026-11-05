"""Capabilities supplied by the outer host when composing platform operations."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from api.credentials import RequestIdentity
from developer_platform.application.dto import AccessContext
from shared.infra.clock import Clock
from shared.infra.settings import Settings

PlatformRequestAuthenticator = Callable[
    [AsyncSession, RequestIdentity, Settings, Clock], Awaitable[AccessContext]
]
