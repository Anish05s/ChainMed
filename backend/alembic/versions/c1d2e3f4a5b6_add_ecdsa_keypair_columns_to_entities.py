"""add_ecdsa_keypair_columns_to_entities

Revision ID: c1d2e3f4a5b6
Revises: 381e6bf8e59b
Create Date: 2026-06-12 10:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = '381e6bf8e59b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ECDSA public/private key columns to entity tables."""
    op.add_column('manufacturers', sa.Column('public_key_pem', sa.Text(), nullable=True))
    op.add_column('manufacturers', sa.Column('private_key_pem', sa.Text(), nullable=True))
    op.add_column('suppliers', sa.Column('public_key_pem', sa.Text(), nullable=True))
    op.add_column('suppliers', sa.Column('private_key_pem', sa.Text(), nullable=True))
    op.add_column('consumers', sa.Column('public_key_pem', sa.Text(), nullable=True))
    op.add_column('consumers', sa.Column('private_key_pem', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove ECDSA keypair columns."""
    op.drop_column('manufacturers', 'public_key_pem')
    op.drop_column('manufacturers', 'private_key_pem')
    op.drop_column('suppliers', 'public_key_pem')
    op.drop_column('suppliers', 'private_key_pem')
    op.drop_column('consumers', 'public_key_pem')
    op.drop_column('consumers', 'private_key_pem')
