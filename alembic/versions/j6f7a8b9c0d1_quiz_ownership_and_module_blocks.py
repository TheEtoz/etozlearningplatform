"""quiz ownership/visibility + module content blocks

Revision ID: j6f7a8b9c0d1
Revises: i5e6f7a8b9c0
Create Date: 2026-07-27 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "i5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Quiz ownership / visibility ---
    op.add_column("quizzes", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.add_column(
        "quizzes",
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=False,
            server_default="public",
        ),
    )
    op.add_column(
        "quizzes", sa.Column("source_quiz_id", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE quizzes
        SET owner_id = (SELECT id FROM users WHERE username = 'demo_teacher' LIMIT 1)
        WHERE owner_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE quizzes
        SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1)
        WHERE owner_id IS NULL
        """
    )
    op.create_index(op.f("ix_quizzes_owner_id"), "quizzes", ["owner_id"])
    op.create_index(op.f("ix_quizzes_visibility"), "quizzes", ["visibility"])
    op.create_foreign_key(
        op.f("fk_quizzes_owner_id_users"),
        "quizzes",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_quizzes_source_quiz_id_quizzes"),
        "quizzes",
        "quizzes",
        ["source_quiz_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "valid_quiz_visibility",
        "quizzes",
        "visibility IN ('public', 'private')",
    )
    op.drop_index(op.f("ix_quizzes_title"), table_name="quizzes")
    op.create_index(op.f("ix_quizzes_title"), "quizzes", ["title"], unique=False)

    # --- Module blocks ---
    op.create_table(
        "module_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "type IN ('lecture', 'text', 'mcq', 'coding')",
            name="valid_module_block_type",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["coding_modules.id"],
            name=op.f("fk_module_blocks_module_id_coding_modules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_module_blocks_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_blocks")),
        sa.UniqueConstraint(
            "module_id",
            "position",
            name="uq_module_blocks_module_position",
        ),
    )
    op.create_index(
        op.f("ix_module_blocks_module_id"), "module_blocks", ["module_id"]
    )
    op.create_index(
        op.f("ix_module_blocks_question_id"), "module_blocks", ["question_id"]
    )

    # Backfill lecture from description
    op.execute(
        """
        INSERT INTO module_blocks (module_id, position, type, payload, question_id)
        SELECT id, 0, 'lecture',
               jsonb_build_object('markdown', COALESCE(description, '')),
               NULL
        FROM coding_modules
        WHERE COALESCE(description, '') <> ''
        """
    )
    # Backfill coding levels after lecture (or from 0)
    op.execute(
        """
        INSERT INTO module_blocks (module_id, position, type, payload, question_id)
        SELECT
            ml.module_id,
            ml.position + CASE
                WHEN COALESCE(cm.description, '') <> '' THEN 1 ELSE 0
            END,
            'coding',
            '{}'::jsonb,
            ml.question_id
        FROM module_levels ml
        JOIN coding_modules cm ON cm.id = ml.module_id
        """
    )

    op.drop_table("module_levels")


def downgrade() -> None:
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
            "module_id", "question_id", name="uq_module_levels_module_question"
        ),
        sa.UniqueConstraint(
            "module_id", "position", name="uq_module_levels_module_position"
        ),
    )
    op.execute(
        """
        INSERT INTO module_levels (module_id, question_id, position)
        SELECT module_id, question_id,
               ROW_NUMBER() OVER (PARTITION BY module_id ORDER BY position) - 1
        FROM module_blocks
        WHERE type = 'coding' AND question_id IS NOT NULL
        """
    )
    op.drop_table("module_blocks")

    op.drop_constraint("valid_quiz_visibility", "quizzes", type_="check")
    op.drop_constraint(
        op.f("fk_quizzes_source_quiz_id_quizzes"), "quizzes", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_quizzes_owner_id_users"), "quizzes", type_="foreignkey"
    )
    op.drop_index(op.f("ix_quizzes_visibility"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_owner_id"), table_name="quizzes")
    op.drop_column("quizzes", "source_quiz_id")
    op.drop_column("quizzes", "visibility")
    op.drop_column("quizzes", "owner_id")
    op.drop_index(op.f("ix_quizzes_title"), table_name="quizzes")
    op.create_index(op.f("ix_quizzes_title"), "quizzes", ["title"], unique=True)
