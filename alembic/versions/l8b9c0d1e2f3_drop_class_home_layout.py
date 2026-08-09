"""Drop unused class home_layout preference.

Revision ID: l8b9c0d1e2f3
Revises: k7a8b9c0d1e2
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "k7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("valid_class_home_layout", "classes", type_="check")
    op.drop_column("classes", "home_layout")


def downgrade() -> None:
    op.add_column(
        "classes",
        sa.Column(
            "home_layout",
            sa.String(length=32),
            server_default="lecture_first",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "valid_class_home_layout",
        "classes",
        "home_layout IN ('lecture_first', 'quizzes_first')",
    )
