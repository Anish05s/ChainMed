"""Merge multiple heads for deployment

Revision ID: de175a67fe29
Revises: 5b0285ff51d6, f8a3b1c2d4e5
Create Date: 2026-06-22 00:15:38.095645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de175a67fe29'
down_revision: Union[str, Sequence[str], None] = ('5b0285ff51d6', 'f8a3b1c2d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
