"""Allow multimedia module blocks.

Revision ID: n0d1e2f3a4b5
Revises: m9c0d1e2f3a4
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "n0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "m9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("valid_module_block_type", "module_blocks", type_="check")
    op.create_check_constraint(
        "valid_module_block_type",
        "module_blocks",
        "type IN ('lecture', 'text', 'media', 'mcq', 'coding')",
    )


def downgrade() -> None:
    op.drop_constraint("valid_module_block_type", "module_blocks", type_="check")
    op.create_check_constraint(
        "valid_module_block_type",
        "module_blocks",
        "type IN ('lecture', 'text', 'mcq', 'coding')",
    )
