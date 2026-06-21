"""add_hash_chain_to_approval_logs

Adds two columns to approval_logs table for the P1.5 integrity chain:
  - previous_hash: the log_hash of the chronologically previous log entry
  - log_hash: SHA-256 of this entry's fields + previous_hash

Existing rows get NULL for both columns (they become the chain's genesis block).
New rows will begin chaining from the first non-NULL log_hash onwards.

Revision ID: f8a3b1c2d4e5
Revises: eab951bc6977
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'f8a3b1c2d4e5'
down_revision = 'eab951bc6977'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('approval_logs', sa.Column('previous_hash', sa.String(), nullable=True))
    op.add_column('approval_logs', sa.Column('log_hash',      sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_logs', 'log_hash')
    op.drop_column('approval_logs', 'previous_hash')
