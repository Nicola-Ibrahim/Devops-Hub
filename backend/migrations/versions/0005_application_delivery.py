"""Durable application generation, delivery and preview workflow records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_application_delivery"
down_revision = "0004_internal_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(32), nullable=False),
        sa.Column("repository_url", sa.String(500), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_preview", sa.Boolean(), nullable=False),
        sa.Column("source_repository", sa.String(200), nullable=True),
        sa.Column("pull_request", sa.Integer(), nullable=True),
        sa.Column("source_branch", sa.String(255), nullable=True),
        sa.Column("source_sha", sa.String(40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','ready','failed','deleting','deleted')",
            name="ck_applications_status",
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["project_environments.id"],
            name=op.f("fk_applications_environment_id_project_environments"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_applications_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_registrations.project_id"],
            name=op.f("fk_applications_project_id_project_registrations"),
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["resources.id"], name=op.f("fk_applications_resource_id_resources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint("project_id", "name", name="uq_application_project_name"),
    )
    op.create_index("ix_applications_project_updated", "applications", ["project_id", "updated_at"])
    op.create_index(
        "ix_applications_preview", "applications", ["source_repository", "pull_request"]
    )
    op.create_table(
        "application_delivery_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('repository','resource','deployment','template_update','preview_cleanup')",
            name="ck_application_delivery_steps_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="ck_application_delivery_steps_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_application_delivery_steps_attempts"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_application_delivery_steps_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_delivery_steps")),
        sa.UniqueConstraint("idempotency_key", name="uq_application_delivery_step_key"),
    )
    op.create_index(
        "ix_application_delivery_due",
        "application_delivery_steps",
        ["status", "next_attempt_at", "claim_expires_at"],
    )
    op.create_table(
        "application_delivery_idempotency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(100), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_application_delivery_idempotency_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_registrations.project_id"],
            name=op.f("fk_application_delivery_idempotency_project_id_project_registrations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_application_delivery_idempotency_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_delivery_idempotency")),
        sa.UniqueConstraint("user_id", "project_id", "route", "key", name="uq_app_delivery_scope"),
    )
    op.create_table(
        "application_deployments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("image_digest", sa.String(300), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','deleted')",
            name="ck_application_deployments_status",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name=op.f("fk_application_deployments_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_application_deployments_requested_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_deployments")),
    )
    op.create_index(
        "ix_application_deployments_history",
        "application_deployments",
        ["application_id", "created_at"],
    )
    op.create_table(
        "application_webhook_events",
        sa.Column("delivery_id", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("repository", sa.String(200), nullable=False),
        sa.Column("pull_request", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("delivery_id", name=op.f("pk_application_webhook_events")),
    )


def downgrade() -> None:
    op.drop_table("application_webhook_events")
    op.drop_index("ix_application_deployments_history", table_name="application_deployments")
    op.drop_table("application_deployments")
    op.drop_table("application_delivery_idempotency")
    op.drop_index("ix_application_delivery_due", table_name="application_delivery_steps")
    op.drop_table("application_delivery_steps")
    op.drop_index("ix_applications_preview", table_name="applications")
    op.drop_index("ix_applications_project_updated", table_name="applications")
    op.drop_table("applications")
