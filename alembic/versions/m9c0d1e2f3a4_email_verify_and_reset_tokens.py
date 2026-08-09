"""Email verification flags and auth email tokens.

Revision ID: m9c0d1e2f3a4
Revises: l8b9c0d1e2f3
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "l8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_users_email_verified"),
        "users",
        ["email_verified"],
        unique=False,
    )
    # Existing accounts keep working after deploy.
    op.execute(
        sa.text(
            "UPDATE users SET email_verified = true, "
            "email_verified_at = COALESCE(email_verified_at, created_at)"
        )
    )

    op.create_table(
        "auth_email_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('verify', 'reset')",
            name="valid_auth_email_token_purpose",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_auth_email_tokens_user_id"),
        "auth_email_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_email_tokens_purpose"),
        "auth_email_tokens",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_email_tokens_token_hash"),
        "auth_email_tokens",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_email_tokens_token_hash"), table_name="auth_email_tokens")
    op.drop_index(op.f("ix_auth_email_tokens_purpose"), table_name="auth_email_tokens")
    op.drop_index(op.f("ix_auth_email_tokens_user_id"), table_name="auth_email_tokens")
    op.drop_table("auth_email_tokens")
    op.drop_index(op.f("ix_users_email_verified"), table_name="users")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
