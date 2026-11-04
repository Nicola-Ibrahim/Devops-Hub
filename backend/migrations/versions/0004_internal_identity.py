"""Add internal password authentication and revocable browser sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0004_internal_identity"
down_revision = "0003_resource_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("credential_version", sa.Integer(), server_default="1", nullable=False)
    )
    op.alter_column("users", "credential_version", server_default=None)
    op.create_check_constraint("credential_version_positive", "users", "credential_version >= 1")
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("selected_project_id", sa.Uuid(), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("credential_version >= 1", name=op.f("ck_browser_sessions_version")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_browser_sessions_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["selected_project_id"],
            ["projects.id"],
            name=op.f("fk_browser_sessions_selected_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_browser_sessions")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_browser_sessions_token_digest")),
    )
    op.create_index(
        "ix_browser_sessions_user_active", "browser_sessions", ["user_id", "revoked_at"]
    )
    op.create_table(
        "browser_login_throttles",
        sa.Column("username_digest", sa.String(64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("failures >= 0", name=op.f("ck_browser_login_throttles_failures")),
        sa.PrimaryKeyConstraint("username_digest", name=op.f("pk_browser_login_throttles")),
    )
    op.create_table(
        "password_setups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_password_setups_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_setups")),
        sa.UniqueConstraint("digest", name=op.f("uq_password_setups_digest")),
    )
    op.create_index("ix_password_setups_user_active", "password_setups", ["user_id", "consumed_at"])
    op.create_table(
        "identity_activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_identity_activity_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["users.id"], name=op.f("fk_identity_activity_subject_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_identity_activity_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_activity")),
    )
    op.create_index("ix_identity_activity_time", "identity_activity", ["subject_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_identity_activity_time", table_name="identity_activity")
    op.drop_table("identity_activity")
    op.drop_index("ix_password_setups_user_active", table_name="password_setups")
    op.drop_table("password_setups")
    op.drop_table("browser_login_throttles")
    op.drop_index("ix_browser_sessions_user_active", table_name="browser_sessions")
    op.drop_table("browser_sessions")
    op.drop_constraint(op.f("ck_users_credential_version_positive"), "users", type_="check")
    op.drop_column("users", "credential_version")
    op.drop_column("users", "password_hash")
