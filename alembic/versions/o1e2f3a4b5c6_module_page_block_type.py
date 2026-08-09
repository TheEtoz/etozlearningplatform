"""Allow page/subtopic marker blocks inside modules.

Revision ID: o1e2f3a4b5c6
Revises: n0d1e2f3a4b5
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "o1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "n0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("valid_module_block_type", "module_blocks", type_="check")
    op.create_check_constraint(
        "valid_module_block_type",
        "module_blocks",
        "type IN ('lecture', 'text', 'media', 'mcq', 'coding', 'page')",
    )


def downgrade() -> None:
    op.drop_constraint("valid_module_block_type", "module_blocks", type_="check")
    op.create_check_constraint(
        "valid_module_block_type",
        "module_blocks",
        "type IN ('lecture', 'text', 'media', 'mcq', 'coding')",
    )
