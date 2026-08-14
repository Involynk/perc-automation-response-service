"""add_resp_knowledge_chunks

Revision ID: 7a3b4c5d6e7f
Revises: c7f58bece6cb
Create Date: 2026-08-14 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7a3b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = 'c7f58bece6cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema:
    1. Ensure pgvector extension is enabled.
    2. Create dedicated resp_knowledge_chunks table.
    3. Add 384-dimensional pgvector column.
    4. Create lookup b-tree indexes and HNSW cosine vector index.
    """
    # 1. Enable pgvector extension if not already present
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create resp_knowledge_chunks table
    op.create_table(
        'resp_knowledge_chunks',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('document_id', sa.String(length=100), nullable=False),
        sa.Column('source_file', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('section', sa.String(length=200), nullable=False),
        sa.Column('heading', sa.String(length=200), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_priority', sa.String(length=50), nullable=False),
        sa.Column('course_id', sa.String(length=50), nullable=True),
        sa.Column('branch_id', sa.String(length=50), nullable=True),
        sa.Column('target_class', sa.String(length=50), nullable=True),
        sa.Column('metadata_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['resp_branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['course_id'], ['resp_courses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Add single 384-dimensional pgvector column for all-MiniLM-L6-v2 embeddings
    op.execute("ALTER TABLE resp_knowledge_chunks ADD COLUMN embedding vector(384);")

    # 4. Create b-tree lookup indexes
    op.create_index(op.f('ix_resp_knowledge_chunks_category'), 'resp_knowledge_chunks', ['category'], unique=False)
    op.create_index(op.f('ix_resp_knowledge_chunks_document_id'), 'resp_knowledge_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_resp_knowledge_chunks_course_id'), 'resp_knowledge_chunks', ['course_id'], unique=False)
    op.create_index(op.f('ix_resp_knowledge_chunks_branch_id'), 'resp_knowledge_chunks', ['branch_id'], unique=False)

    # 5. Create HNSW index for high-speed cosine vector search
    op.execute(
        "CREATE INDEX resp_knowledge_chunks_embedding_hnsw_idx "
        "ON resp_knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )


def downgrade() -> None:
    """Downgrade schema: cleanly drops resp_knowledge_chunks table and indexes."""
    op.drop_table('resp_knowledge_chunks')
