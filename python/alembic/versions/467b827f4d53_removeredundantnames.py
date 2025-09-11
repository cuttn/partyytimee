"""removeRedundantNames

Revision ID: 467b827f4d53
Revises: 79f6ce373ad9
Create Date: 2025-07-30 19:35:39.427037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '467b827f4d53'
down_revision: Union[str, Sequence[str], None] = '79f6ce373ad9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove redundant user fields
    op.drop_column('user', 'display_name')
    op.drop_column('user', 'first_name')
    op.drop_column('user', 'last_name')


def downgrade() -> None:
    """Downgrade schema."""
    # Add back the redundant fields (for rollback purposes)
    op.add_column('user', sa.Column('display_name', sa.String(), nullable=True))
    op.add_column('user', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('user', sa.Column('last_name', sa.String(), nullable=True))
