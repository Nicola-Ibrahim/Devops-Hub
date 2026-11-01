"""SQLAlchemy implementation of identity's authentication read port."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from identity.application.errors import IdentityUnavailable
from identity.domain.credentials import CredentialSnapshot
from identity.infra.persistence.models import ApiToken, Membership, User


class SQLAuthenticationReader:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def find_by_digest(self, digest: str) -> CredentialSnapshot | None:
        try:
            with self._sessions() as session:
                row = session.execute(
                    select(ApiToken, User.active, Membership.role)
                    .join(User, User.id == ApiToken.user_id)
                    .outerjoin(
                        Membership,
                        (Membership.user_id == ApiToken.user_id)
                        & (Membership.project_id == ApiToken.project_id),
                    )
                    .where(ApiToken.digest == digest)
                ).one_or_none()
                if row is None:
                    return None
                token, active, role = row
                return CredentialSnapshot(
                    token_id=token.id,
                    user_id=token.user_id,
                    project_id=token.project_id,
                    role=role,
                    scopes=tuple(token.scopes),
                    user_active=active,
                    expires_at=token.expires_at,
                    revoked_at=token.revoked_at,
                )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc
