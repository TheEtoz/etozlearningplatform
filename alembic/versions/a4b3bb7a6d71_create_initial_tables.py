"""create initial tables

Revision ID: a4b3bb7a6d71
Revises: 
Create Date: 2026-07-26 14:14:29.968798

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4b3bb7a6d71"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users, questions, submissions, and progress tables."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
    )
    op.create_index(
        op.f("ix_users_username"),
        "users",
        ["username"],
        unique=True,
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column(
            "language",
            sa.String(length=50),
            server_default="python",
            nullable=False,
        ),
        sa.Column("choices", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("starter_code", sa.Text(), nullable=True),
        sa.Column("test_cases", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name=op.f("ck_questions_valid_difficulty"),
        ),
        sa.CheckConstraint(
            "type IN ('mcq', 'coding')",
            name=op.f("ck_questions_valid_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    for column_name in ("difficulty", "language", "title", "topic", "type"):
        op.create_index(
            op.f(f"ix_questions_{column_name}"),
            "questions",
            [column_name],
            unique=False,
        )

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "score",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code IS NOT NULL OR answer IS NOT NULL",
            name=op.f("ck_submissions_has_response"),
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name=op.f("ck_submissions_score_range"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'error')",
            name=op.f("ck_submissions_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_submissions_question_id_questions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_submissions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    for column_name in ("created_at", "question_id", "status", "user_id"):
        op.create_index(
            op.f(f"ix_submissions_{column_name}"),
            "submissions",
            [column_name],
            unique=False,
        )

    op.create_table(
        "progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column(
            "questions_attempted",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "questions_correct",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "accuracy",
            sa.Numeric(precision=5, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.CheckConstraint(
            "accuracy >= 0 AND accuracy <= 100",
            name=op.f("ck_progress_accuracy_range"),
        ),
        sa.CheckConstraint(
            "questions_attempted >= 0",
            name=op.f("ck_progress_attempted_non_negative"),
        ),
        sa.CheckConstraint(
            "questions_correct >= 0 "
            "AND questions_correct <= questions_attempted",
            name=op.f("ck_progress_correct_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_progress_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_progress")),
        sa.UniqueConstraint(
            "user_id",
            "topic",
            name="uq_progress_user_topic",
        ),
    )
    op.create_index(
        op.f("ix_progress_topic"),
        "progress",
        ["topic"],
        unique=False,
    )
    op.create_index(
        op.f("ix_progress_user_id"),
        "progress",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove all initial tables in reverse dependency order."""
    op.drop_index(op.f("ix_progress_user_id"), table_name="progress")
    op.drop_index(op.f("ix_progress_topic"), table_name="progress")
    op.drop_table("progress")

    for column_name in ("user_id", "status", "question_id", "created_at"):
        op.drop_index(
            op.f(f"ix_submissions_{column_name}"),
            table_name="submissions",
        )
    op.drop_table("submissions")

    for column_name in ("type", "topic", "title", "language", "difficulty"):
        op.drop_index(
            op.f(f"ix_questions_{column_name}"),
            table_name="questions",
        )
    op.drop_table("questions")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
