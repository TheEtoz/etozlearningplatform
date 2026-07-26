"""add quiz_attempts for student score history

Revision ID: c8e1a42b9d33
Revises: b7c2d91e4f10
Create Date: 2026-07-26 15:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e1a42b9d33"
down_revision: str | Sequence[str] | None = "b7c2d91e4f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create quiz_attempts so completed scores are stored for statistics."""

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("questions_total", sa.Integer(), nullable=False),
        sa.Column("questions_answered", sa.Integer(), nullable=False),
        sa.Column("questions_correct", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="completed",
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "questions_answered >= 0 "
            "AND questions_answered <= questions_total",
            name=op.f("ck_quiz_attempts_answered_valid"),
        ),
        sa.CheckConstraint(
            "questions_correct >= 0 "
            "AND questions_correct <= questions_answered",
            name=op.f("ck_quiz_attempts_correct_valid"),
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name=op.f("ck_quiz_attempts_score_range"),
        ),
        sa.CheckConstraint(
            "status IN ('completed')",
            name=op.f("ck_quiz_attempts_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_attempts_quiz_id_quizzes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_quiz_attempts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_attempts")),
    )
    op.create_index(
        op.f("ix_quiz_attempts_completed_at"),
        "quiz_attempts",
        ["completed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quiz_attempts_quiz_id"),
        "quiz_attempts",
        ["quiz_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quiz_attempts_user_id"),
        "quiz_attempts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop quiz attempt history."""

    op.drop_index(op.f("ix_quiz_attempts_user_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_quiz_id"), table_name="quiz_attempts")
    op.drop_index(
        op.f("ix_quiz_attempts_completed_at"),
        table_name="quiz_attempts",
    )
    op.drop_table("quiz_attempts")
