"""question ownership/visibility and class announcements

Revision ID: g3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-07-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("owner_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column(
            "visibility",
            sa.String(length=20),
            server_default="public",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_questions_owner_id"), "questions", ["owner_id"])
    op.create_index(op.f("ix_questions_visibility"), "questions", ["visibility"])
    op.create_foreign_key(
        op.f("fk_questions_owner_id_users"),
        "questions",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "valid_question_visibility",
        "questions",
        "visibility IN ('public', 'private')",
    )

    op.create_table(
        "class_announcements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_class_announcements_author_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_class_announcements_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_announcements")),
    )
    op.create_index(
        op.f("ix_class_announcements_class_id"),
        "class_announcements",
        ["class_id"],
    )
    op.create_index(
        op.f("ix_class_announcements_author_id"),
        "class_announcements",
        ["author_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_class_announcements_author_id"),
        table_name="class_announcements",
    )
    op.drop_index(
        op.f("ix_class_announcements_class_id"),
        table_name="class_announcements",
    )
    op.drop_table("class_announcements")

    op.drop_constraint("valid_question_visibility", "questions", type_="check")
    op.drop_constraint(
        op.f("fk_questions_owner_id_users"), "questions", type_="foreignkey"
    )
    op.drop_index(op.f("ix_questions_visibility"), table_name="questions")
    op.drop_index(op.f("ix_questions_owner_id"), table_name="questions")
    op.drop_column("questions", "visibility")
    op.drop_column("questions", "owner_id")
