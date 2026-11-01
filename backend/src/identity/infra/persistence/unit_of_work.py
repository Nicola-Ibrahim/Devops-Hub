"""Transactional identity writes implemented over the shared technical database."""

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import SessionTransaction

from identity.application.errors import IdentityUnavailable
from identity.domain.records import AuditRecord, IdentitySnapshot, TokenSnapshot
from identity.infra.persistence.models import ApiToken, Membership, Project, User
from shared.infra.persistence.audit import AuditEvent


class SQLIdentityUnitOfWork:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._session: Session | None = None
        self._transaction: SessionTransaction | None = None

    def __enter__(self) -> "SQLIdentityUnitOfWork":
        try:
            self._session = self._sessions()
            self._transaction = self._session.begin()
            self._transaction.__enter__()
            return self
        except SQLAlchemyError as error:
            if self._session is not None:
                try:
                    self._session.close()
                except BaseException:
                    error.add_note(
                        "Identity session cleanup failed; the original failure was preserved."
                    )
            self._session = None
            self._transaction = None
            raise IdentityUnavailable() from error

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        assert self._session is not None and self._transaction is not None
        session = self._session
        transaction = self._transaction
        pending: BaseException | None = None
        try:
            try:
                transaction.__exit__(exc_type, exc, traceback)
            except SQLAlchemyError as error:
                if exc is not None:
                    exc.add_note(
                        "Identity transaction rollback failed; the original failure was preserved."
                    )
                else:
                    pending = IdentityUnavailable()
                    pending.__cause__ = error
            except BaseException as error:
                if exc is not None:
                    exc.add_note(
                        "Identity transaction cleanup failed; the original failure was preserved."
                    )
                else:
                    pending = error
        finally:
            try:
                session.close()
            except SQLAlchemyError as error:
                if exc is not None:
                    exc.add_note(
                        "Identity session cleanup failed; the original failure was preserved."
                    )
                elif pending is not None:
                    pending.add_note(
                        "Identity session cleanup failed; the original failure was preserved."
                    )
                else:
                    pending = IdentityUnavailable()
                    pending.__cause__ = error
            except BaseException as error:
                if exc is not None:
                    exc.add_note(
                        "Identity session cleanup failed; the original failure was preserved."
                    )
                elif pending is not None:
                    pending.add_note(
                        "Identity session cleanup failed; the original failure was preserved."
                    )
                else:
                    pending = error
            self._session = None
            self._transaction = None
        if pending is not None:
            raise pending
        return None

    def ensure_identity(
        self,
        *,
        user_name: str,
        project_name: str,
        new_role: str,
    ) -> IdentitySnapshot:
        session = self._active_session()
        try:
            user = session.scalar(select(User).where(User.name == user_name))
            if user is None:
                user = User(name=user_name)
                session.add(user)
                session.flush()
            project = session.scalar(select(Project).where(Project.name == project_name))
            if project is None:
                project = Project(name=project_name)
                session.add(project)
                session.flush()
            membership = session.get(Membership, (user.id, project.id))
            if membership is None:
                session.add(Membership(user_id=user.id, project_id=project.id, role=new_role))
            return IdentitySnapshot(
                user_id=user.id,
                project_id=project.id,
                user_active=user.active,
            )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    def add_token(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        digest: str,
        scopes: tuple[str, ...],
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID:
        session = self._active_session()
        try:
            record = ApiToken(
                user_id=user_id,
                project_id=project_id,
                digest=digest,
                scopes=list(scopes),
                created_at=created_at,
                expires_at=expires_at,
                revoked_at=None,
            )
            session.add(record)
            session.flush()
            return record.id
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    def append_audit(self, event: AuditRecord) -> None:
        session = self._active_session()
        try:
            session.add(
                AuditEvent(
                    actor_id=event.actor_id,
                    project_id=event.project_id,
                    action=event.action,
                    outcome=event.outcome,
                    request_id=event.request_id,
                )
            )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    def find_token(self, token_id: UUID) -> TokenSnapshot | None:
        session = self._active_session()
        try:
            token = session.get(ApiToken, token_id)
            if token is None:
                return None
            return TokenSnapshot(token.id, token.user_id, token.project_id, token.revoked_at)
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    def set_revoked(self, token_id: UUID, revoked_at: datetime) -> None:
        session = self._active_session()
        try:
            token = session.get(ApiToken, token_id)
            if token is not None:
                token.revoked_at = revoked_at
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    def _active_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Identity unit of work is not active")
        return self._session
