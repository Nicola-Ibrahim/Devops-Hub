"""Add project references, environments, and resource activity ledger."""

import sqlalchemy as sa
from alembic import op

revision = "0002_request_ledger"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("name", name=op.f("uq_teams_name")),
    )
    op.create_table(
        "project_registrations",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owning_team_id", sa.Uuid(), nullable=True),
        sa.Column("owning_team_name", sa.String(length=100), nullable=True),
        sa.Column("repository", sa.String(length=200), nullable=True),
        sa.Column("configured", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owning_team_id"],
            ["teams.id"],
            name=op.f("fk_project_registrations_owning_team_id_teams"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_registrations_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_registrations")),
        sa.UniqueConstraint("name", name=op.f("uq_project_registrations_name")),
    )

    # Preserve existing project identities without claiming team or repository
    # ownership that was not previously recorded.
    op.execute(
        sa.text(
            "INSERT INTO project_registrations "
            "(project_id, name, owning_team_id, owning_team_name, repository, configured) "
            "SELECT id, name, NULL, NULL, NULL, FALSE FROM projects"
        )
    )

    op.create_table(
        "project_environments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_registrations.project_id"],
            name=op.f("fk_project_environments_project_id_project_registrations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_environments")),
        sa.UniqueConstraint("project_id", "name", name="uq_project_environment"),
    )
    op.add_column("resources", sa.Column("environment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_resources_environment_id_project_environments"),
        "resources",
        "project_environments",
        ["environment_id"],
        ["id"],
    )

    op.create_table(
        "resource_activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_resource_activity_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_resource_activity_operation_id_operations"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_resource_activity_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_resource_activity_resource_id_resources"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_activity")),
    )
    op.create_index(
        "ix_resource_activity_time",
        "resource_activity",
        ["resource_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_resource_activity_time", table_name="resource_activity")
    op.drop_table("resource_activity")
    op.drop_constraint(
        op.f("fk_resources_environment_id_project_environments"),
        "resources",
        type_="foreignkey",
    )
    op.drop_column("resources", "environment_id")
    op.drop_table("project_environments")
    op.drop_table("project_registrations")
    op.drop_table("teams")
