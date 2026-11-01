"""The only place that constructs both use cases and their concrete adapters."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine

from api.dependencies import ApiServices
from bootstrap.schema import registered_metadata
from bootstrap.settings import SCHEMA_REVISION, Settings
from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.permissions import ALL_SCOPES
from identity.application.authenticate import Authenticate
from identity.application.issue_token import IssueToken
from identity.application.revoke_token import RevokeToken
from identity.infra.persistence.store import SQLAuthenticationReader
from identity.infra.persistence.unit_of_work import SQLIdentityUnitOfWork
from identity.infra.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.persistence.database import create_session_factory
from shared.infra.readiness import SQLReadinessProbe


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ApplicationServices:
    api: ApiServices
    issue_token: IssueToken
    revoke_token: RevokeToken


def build_services(settings: Settings, engine: Engine) -> ApplicationServices:
    registered_metadata()
    sessions = create_session_factory(engine)
    hasher = PepperedTokenHasher(settings.token_pepper.get_secret_value())
    authenticate = Authenticate(SQLAuthenticationReader(sessions), hasher, utc_now)
    readiness = SQLReadinessProbe(engine, SCHEMA_REVISION)
    return ApplicationServices(
        api=ApiServices(authenticate, ReadCatalog(), readiness.inspect),
        issue_token=IssueToken(
            transactions=lambda: SQLIdentityUnitOfWork(sessions),
            hasher=hasher,
            generator=SecureTokenGenerator(),
            clock=utc_now,
            allowed_scopes=ALL_SCOPES,
            default_scopes=ALL_SCOPES,
        ),
        revoke_token=RevokeToken(lambda: SQLIdentityUnitOfWork(sessions), utc_now),
    )
