"""class home layout preference (lecture vs quizzes first)

Revision ID: k7a8b9c0d1e2
Revises: j6f7a8b9c0d1
Create Date: 2026-08-02 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "j6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "classes",
        sa.Column(
            "home_layout",
            sa.String(length=32),
            nullable=False,
            server_default="lecture_first",
        ),
    )
    op.create_check_constraint(
        "valid_class_home_layout",
        "classes",
        "home_layout IN ('lecture_first', 'quizzes_first')",
    )


def downgrade() -> None:
    op.drop_constraint("valid_class_home_layout", "classes", type_="check")
    op.drop_column("classes", "home_layout")
