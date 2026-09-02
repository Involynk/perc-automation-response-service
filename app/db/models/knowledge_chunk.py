from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeChunkModel(Base):
    """
    SQLAlchemy 2.0 ORM model for storing RAG knowledge chunks in PostgreSQL.
    Maps to 'resp_knowledge_chunks' table.
    """
    __tablename__ = "resp_knowledge_chunks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(200), nullable=False)
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_priority: Mapped[str] = mapped_column(String(50), nullable=False)

    course_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("resp_courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    branch_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("resp_branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_class: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
