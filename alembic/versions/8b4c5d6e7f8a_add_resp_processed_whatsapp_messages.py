"""add_resp_processed_whatsapp_messages

Revision ID: 8b4c5d6e7f8a
Revises: 7a3b4c5d6e7f
Create Date: 2026-08-19 20:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8b4c5d6e7f8a'
down_revision: Union[str, Sequence[str], None] = '7a3b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create resp_processed_whatsapp_messages table for webhook idempotency."""
    op.create_table(
        'resp_processed_whatsapp_messages',
        sa.Column('wamid', sa.String(length=255), nullable=False),
        sa.Column('sender_phone', sa.String(length=50), nullable=False),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PROCESSED'),
        sa.Column('response_intent', sa.String(length=100), nullable=True),
        sa.Column('outbound_wamid', sa.String(length=255), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('wamid')
    )
    op.create_index('ix_resp_processed_whatsapp_messages_wamid', 'resp_processed_whatsapp_messages', ['wamid'], unique=False)
    op.create_index('ix_resp_processed_whatsapp_messages_sender_phone', 'resp_processed_whatsapp_messages', ['sender_phone'], unique=False)


def downgrade() -> None:
    """Drop resp_processed_whatsapp_messages table."""
    op.drop_index('ix_resp_processed_whatsapp_messages_sender_phone', table_name='resp_processed_whatsapp_messages')
    op.drop_index('ix_resp_processed_whatsapp_messages_wamid', table_name='resp_processed_whatsapp_messages')
    op.drop_table('resp_processed_whatsapp_messages')
