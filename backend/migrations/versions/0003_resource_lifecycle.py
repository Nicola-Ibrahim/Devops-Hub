"""Allow system lifecycle events without inventing a user identity."""

import sqlalchemy as sa
from alembic import op

revision = "0003_resource_lifecycle"
down_revision = "0002_request_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("resource_activity", "actor_id", existing_type=sa.Uuid(), nullable=True)
    op.create_table(
        "provider_orphans",
        sa.Column("resource_id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("provider_orphans")
    # System events cannot be attributed to a fabricated user on downgrade.
    op.execute("DELETE FROM resource_activity WHERE actor_id IS NULL")
    op.alter_column("resource_activity", "actor_id", existing_type=sa.Uuid(), nullable=False)
