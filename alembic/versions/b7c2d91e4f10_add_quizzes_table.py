"""add quizzes table and question quiz_id

Revision ID: b7c2d91e4f10
Revises: a4b3bb7a6d71
Create Date: 2026-07-26 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c2d91e4f10"
down_revision: str | Sequence[str] | None = "a4b3bb7a6d71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create quizzes and attach questions to teacher-designed packs."""

    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column(
            "is_timed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(is_timed = false AND duration_seconds IS NULL) OR "
            "(is_timed = true AND duration_seconds > 0)",
            name=op.f("ck_quizzes_timed_duration_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quizzes")),
    )
    op.create_index(op.f("ix_quizzes_title"), "quizzes", ["title"], unique=True)
    op.create_index(op.f("ix_quizzes_topic"), "quizzes", ["topic"], unique=False)

    op.add_column(
        "questions",
        sa.Column("quiz_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_questions_quiz_id"),
        "questions",
        ["quiz_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_questions_quiz_id_quizzes"),
        "questions",
        "quizzes",
        ["quiz_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove quiz ownership from questions and drop quizzes."""

    op.drop_constraint(
        op.f("fk_questions_quiz_id_quizzes"),
        "questions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_questions_quiz_id"), table_name="questions")
    op.drop_column("questions", "quiz_id")
    op.drop_index(op.f("ix_quizzes_topic"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_title"), table_name="quizzes")
    op.drop_table("quizzes")
