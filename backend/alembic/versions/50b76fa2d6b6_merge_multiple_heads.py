"""merge multiple heads

Revision ID: 50b76fa2d6b6
Revises: 0f4fbf8c80ae, c1d2e3f4a5b6
Create Date: 2026-06-12 17:17:55.652869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50b76fa2d6b6'
down_revision: Union[str, Sequence[str], None] = ('0f4fbf8c80ae', 'c1d2e3f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
