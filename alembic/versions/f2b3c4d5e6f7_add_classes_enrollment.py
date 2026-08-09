"""add classes, enrollment, and class-scoped attempts

Revision ID: f2b3c4d5e6f7
Revises: e1a2b3c4d5e6
Create Date: 2026-07-27 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "e1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create class tables and class_id columns on attempts/submissions."""

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("enrollment_code", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'private')",
            name="valid_class_visibility",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_classes_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classes")),
        sa.UniqueConstraint(
            "enrollment_code",
            name=op.f("uq_classes_enrollment_code"),
        ),
    )
    op.create_index(op.f("ix_classes_title"), "classes", ["title"], unique=False)
    op.create_index(op.f("ix_classes_owner_id"), "classes", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_classes_visibility"), "classes", ["visibility"], unique=False
    )
    op.create_index(
        op.f("ix_classes_enrollment_code"),
        "classes",
        ["enrollment_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classes_is_active"), "classes", ["is_active"], unique=False
    )

    op.create_table(
        "class_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_class_enrollments_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_class_enrollments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_enrollments")),
        sa.UniqueConstraint(
            "class_id",
            "user_id",
            name="uq_class_enrollments_class_user",
        ),
    )
    op.create_index(
        op.f("ix_class_enrollments_class_id"),
        "class_enrollments",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_class_enrollments_user_id"),
        "class_enrollments",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "class_quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "is_published",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_class_quizzes_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_class_quizzes_quiz_id_quizzes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_quizzes")),
        sa.UniqueConstraint(
            "class_id",
            "quiz_id",
            name="uq_class_quizzes_class_quiz",
        ),
        sa.UniqueConstraint(
            "class_id",
            "position",
            name="uq_class_quizzes_class_position",
        ),
    )
    op.create_index(
        op.f("ix_class_quizzes_class_id"),
        "class_quizzes",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_class_quizzes_quiz_id"),
        "class_quizzes",
        ["quiz_id"],
        unique=False,
    )

    op.create_table(
        "class_modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "is_published",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_class_modules_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["coding_modules.id"],
            name=op.f("fk_class_modules_module_id_coding_modules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_modules")),
        sa.UniqueConstraint(
            "class_id",
            "module_id",
            name="uq_class_modules_class_module",
        ),
        sa.UniqueConstraint(
            "class_id",
            "position",
            name="uq_class_modules_class_position",
        ),
    )
    op.create_index(
        op.f("ix_class_modules_class_id"),
        "class_modules",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_class_modules_module_id"),
        "class_modules",
        ["module_id"],
        unique=False,
    )

    op.add_column(
        "quiz_attempts",
        sa.Column("class_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_quiz_attempts_class_id"),
        "quiz_attempts",
        ["class_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_quiz_attempts_class_id_classes"),
        "quiz_attempts",
        "classes",
        ["class_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "submissions",
        sa.Column("class_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_submissions_class_id"),
        "submissions",
        ["class_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_submissions_class_id_classes"),
        "submissions",
        "classes",
        ["class_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop class tables and class_id columns."""

    op.drop_constraint(
        op.f("fk_submissions_class_id_classes"),
        "submissions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_submissions_class_id"), table_name="submissions")
    op.drop_column("submissions", "class_id")

    op.drop_constraint(
        op.f("fk_quiz_attempts_class_id_classes"),
        "quiz_attempts",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_quiz_attempts_class_id"), table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "class_id")

    op.drop_index(op.f("ix_class_modules_module_id"), table_name="class_modules")
    op.drop_index(op.f("ix_class_modules_class_id"), table_name="class_modules")
    op.drop_table("class_modules")

    op.drop_index(op.f("ix_class_quizzes_quiz_id"), table_name="class_quizzes")
    op.drop_index(op.f("ix_class_quizzes_class_id"), table_name="class_quizzes")
    op.drop_table("class_quizzes")

    op.drop_index(
        op.f("ix_class_enrollments_user_id"), table_name="class_enrollments"
    )
    op.drop_index(
        op.f("ix_class_enrollments_class_id"), table_name="class_enrollments"
    )
    op.drop_table("class_enrollments")

    op.drop_index(op.f("ix_classes_is_active"), table_name="classes")
    op.drop_index(op.f("ix_classes_enrollment_code"), table_name="classes")
    op.drop_index(op.f("ix_classes_visibility"), table_name="classes")
    op.drop_index(op.f("ix_classes_owner_id"), table_name="classes")
    op.drop_index(op.f("ix_classes_title"), table_name="classes")
    op.drop_table("classes")
