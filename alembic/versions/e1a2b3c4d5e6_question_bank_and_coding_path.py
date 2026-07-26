"""question bank M2M, topics, coding path modules

Revision ID: e1a2b3c4d5e6
Revises: d9f4b18c2e01
Create Date: 2026-07-26 16:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d9f4b18c2e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create bank/path tables and migrate quiz_id + topic strings."""

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topics")),
        sa.UniqueConstraint("name", name=op.f("uq_topics_name")),
    )
    op.create_index(op.f("ix_topics_name"), "topics", ["name"], unique=False)

    op.create_table(
        "question_topics",
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_question_topics_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_question_topics_topic_id_topics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "question_id",
            "topic_id",
            name=op.f("pk_question_topics"),
        ),
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_questions_quiz_id_quizzes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_quiz_questions_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_questions")),
        sa.UniqueConstraint(
            "quiz_id",
            "question_id",
            name="uq_quiz_questions_quiz_question",
        ),
        sa.UniqueConstraint(
            "quiz_id",
            "position",
            name="uq_quiz_questions_quiz_position",
        ),
    )
    op.create_index(
        op.f("ix_quiz_questions_quiz_id"),
        "quiz_questions",
        ["quiz_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quiz_questions_question_id"),
        "quiz_questions",
        ["question_id"],
        unique=False,
    )

    op.create_table(
        "coding_modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("difficulty_label", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coding_modules")),
        sa.UniqueConstraint("title", name=op.f("uq_coding_modules_title")),
    )
    op.create_index(
        op.f("ix_coding_modules_title"),
        "coding_modules",
        ["title"],
        unique=False,
    )
    op.create_index(
        op.f("ix_coding_modules_position"),
        "coding_modules",
        ["position"],
        unique=False,
    )

    op.create_table(
        "module_levels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["coding_modules.id"],
            name=op.f("fk_module_levels_module_id_coding_modules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_module_levels_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_levels")),
        sa.UniqueConstraint(
            "module_id",
            "question_id",
            name="uq_module_levels_module_question",
        ),
        sa.UniqueConstraint(
            "module_id",
            "position",
            name="uq_module_levels_module_position",
        ),
    )
    op.create_index(
        op.f("ix_module_levels_module_id"),
        "module_levels",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_module_levels_question_id"),
        "module_levels",
        ["question_id"],
        unique=False,
    )

    # Migrate existing quiz memberships and topics.
    conn = op.get_bind()
    questions = conn.execute(
        sa.text(
            "SELECT id, quiz_id, topic FROM questions "
            "ORDER BY quiz_id NULLS LAST, id"
        )
    ).fetchall()

    topic_ids: dict[str, int] = {}
    positions: dict[int, int] = {}

    for question_id, quiz_id, topic_name in questions:
        name = (topic_name or "general").strip().lower()
        if name not in topic_ids:
            topic_id = conn.execute(
                sa.text(
                    "INSERT INTO topics (name) VALUES (:name) RETURNING id"
                ),
                {"name": name},
            ).scalar_one()
            topic_ids[name] = topic_id
        else:
            topic_id = topic_ids[name]

        conn.execute(
            sa.text(
                "INSERT INTO question_topics (question_id, topic_id) "
                "VALUES (:qid, :tid) ON CONFLICT DO NOTHING"
            ),
            {"qid": question_id, "tid": topic_id},
        )

        if quiz_id is not None:
            pos = positions.get(quiz_id, 0)
            conn.execute(
                sa.text(
                    "INSERT INTO quiz_questions "
                    "(quiz_id, question_id, position) "
                    "VALUES (:quiz_id, :question_id, :position)"
                ),
                {
                    "quiz_id": quiz_id,
                    "question_id": question_id,
                    "position": pos,
                },
            )
            positions[quiz_id] = pos + 1

    op.drop_constraint(
        op.f("fk_questions_quiz_id_quizzes"),
        "questions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_questions_quiz_id"), table_name="questions")
    op.drop_column("questions", "quiz_id")
    op.alter_column(
        "questions",
        "topic",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.alter_column(
        "quizzes",
        "topic",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    """Best-effort reverse migration (membership restored loosely)."""

    op.add_column(
        "questions",
        sa.Column("quiz_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_questions_quiz_id", "questions", ["quiz_id"])
    op.create_foreign_key(
        "fk_questions_quiz_id_quizzes",
        "questions",
        "quizzes",
        ["quiz_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "questions",
        "topic",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "quizzes",
        "topic",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.drop_table("module_levels")
    op.drop_table("coding_modules")
    op.drop_table("quiz_questions")
    op.drop_table("question_topics")
    op.drop_table("topics")
