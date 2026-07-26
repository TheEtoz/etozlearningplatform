"""add user role for teacher/admin access

Revision ID: d9f4b18c2e01
Revises: c8e1a42b9d33
Create Date: 2026-07-26 16:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f4b18c2e01"
down_revision: str | Sequence[str] | None = "c8e1a42b9d33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add role column so teachers can manage questions."""

    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="student",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_check_constraint(
        "valid_user_role",
        "users",
        "role IN ('student', 'admin')",
    )


def downgrade() -> None:
    """Remove role column."""

    op.drop_constraint("valid_user_role", "users", type_="check")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "role")
