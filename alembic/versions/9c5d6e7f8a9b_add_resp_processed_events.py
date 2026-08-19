"""add_resp_processed_events

Revision ID: 9c5d6e7f8a9b
Revises: 8b4c5d6e7f8a
Create Date: 2026-08-19 21:28:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9c5d6e7f8a9b'
down_revision: Union[str, Sequence[str], None] = '8b4c5d6e7f8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create resp_processed_events table for Kafka cluster-wide durable idempotency."""
    op.create_table(
        'resp_processed_events',
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('topic', sa.String(length=100), nullable=False),
        sa.Column('lead_id', sa.String(length=100), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_resp_processed_events_event_id', 'resp_processed_events', ['event_id'], unique=False)
    op.create_index('ix_resp_processed_events_lead_id', 'resp_processed_events', ['lead_id'], unique=False)


def downgrade() -> None:
    """Drop resp_processed_events table."""
    op.drop_index('ix_resp_processed_events_lead_id', table_name='resp_processed_events')
    op.drop_index('ix_resp_processed_events_event_id', table_name='resp_processed_events')
    op.drop_table('resp_processed_events')
