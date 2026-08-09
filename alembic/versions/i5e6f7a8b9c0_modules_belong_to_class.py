"""coding modules belong to a class

Revision ID: i5e6f7a8b9c0
Revises: h4d5e6f7a8b9
Create Date: 2026-07-27 10:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "h4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coding_modules",
        sa.Column("class_id", sa.Integer(), nullable=True),
    )

    # Prefer an existing class_modules link; otherwise first class; else leave null.
    op.execute(
        """
        UPDATE coding_modules AS m
        SET class_id = sub.class_id
        FROM (
            SELECT DISTINCT ON (module_id) module_id, class_id
            FROM class_modules
            ORDER BY module_id, position, id
        ) AS sub
        WHERE m.id = sub.module_id
        """
    )
    op.execute(
        """
        UPDATE coding_modules
        SET class_id = (SELECT id FROM classes ORDER BY id LIMIT 1)
        WHERE class_id IS NULL
          AND EXISTS (SELECT 1 FROM classes)
        """
    )
    # Orphan modules with no class cannot be NOT NULL — delete them.
    op.execute("DELETE FROM coding_modules WHERE class_id IS NULL")

    op.alter_column("coding_modules", "class_id", nullable=False)
    op.create_index(
        op.f("ix_coding_modules_class_id"),
        "coding_modules",
        ["class_id"],
    )
    op.create_foreign_key(
        op.f("fk_coding_modules_class_id_classes"),
        "coding_modules",
        "classes",
        ["class_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(op.f("uq_coding_modules_title"), "coding_modules", type_="unique")
    op.create_unique_constraint(
        "uq_coding_modules_class_id_title",
        "coding_modules",
        ["class_id", "title"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_coding_modules_class_id_title", "coding_modules", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_coding_modules_title"), "coding_modules", ["title"]
    )
    op.drop_constraint(
        op.f("fk_coding_modules_class_id_classes"),
        "coding_modules",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_coding_modules_class_id"), table_name="coding_modules")
    op.drop_column("coding_modules", "class_id")
