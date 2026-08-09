"""subjects contain areas (topics); scope area names per subject

Revision ID: h4d5e6f7a8b9
Revises: g3c4d5e6f7a8
Create Date: 2026-07-27 10:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "g3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("name", name=op.f("uq_subjects_name")),
    )
    op.create_index(op.f("ix_subjects_name"), "subjects", ["name"], unique=False)

    op.add_column("topics", sa.Column("subject_id", sa.Integer(), nullable=True))

    # Default subject for existing areas
    op.execute("INSERT INTO subjects (name) VALUES ('python')")
    op.execute(
        "UPDATE topics SET subject_id = (SELECT id FROM subjects WHERE name = 'python')"
    )
    # Seed common subjects
    op.execute(
        "INSERT INTO subjects (name) VALUES ('math') ON CONFLICT (name) DO NOTHING"
    )
    op.execute(
        "INSERT INTO subjects (name) VALUES ('java') ON CONFLICT (name) DO NOTHING"
    )

    op.alter_column("topics", "subject_id", nullable=False)
    op.create_index(op.f("ix_topics_subject_id"), "topics", ["subject_id"])
    op.create_foreign_key(
        op.f("fk_topics_subject_id_subjects"),
        "topics",
        "subjects",
        ["subject_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Replace global unique name with per-subject unique name
    op.drop_constraint(op.f("uq_topics_name"), "topics", type_="unique")
    op.create_unique_constraint(
        "uq_topics_subject_id_name",
        "topics",
        ["subject_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_topics_subject_id_name", "topics", type_="unique")
    op.create_unique_constraint(op.f("uq_topics_name"), "topics", ["name"])
    op.drop_constraint(
        op.f("fk_topics_subject_id_subjects"), "topics", type_="foreignkey"
    )
    op.drop_index(op.f("ix_topics_subject_id"), table_name="topics")
    op.drop_column("topics", "subject_id")
    op.drop_index(op.f("ix_subjects_name"), table_name="subjects")
    op.drop_table("subjects")
