from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, JSON, func
from app.db.base import Base


class ConversationModel(Base):
    """
    Shared centralized 'conversations' table matching lead-capture-service schema.
    Stores active conversation sessions for leads and ordered message streams
    inside metadata['messages'].
    """
    __tablename__ = "conversations"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid4()))
    lead_id = Column(String(255), nullable=False, index=True, doc="Lead ID associated with this conversation")
    channel_id = Column(String(100), nullable=False, default="whatsapp", doc="Channel identifier (e.g. chan_whatsapp)")
    status = Column(String(50), nullable=False, default="active", doc="Session status ('active', 'closed')")
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Timestamp when conversation session started")
    metadata_json = Column("metadata", JSON, nullable=True, doc="JSON metadata payload storing array of conversation messages under 'messages'")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} lead_id={self.lead_id} status={self.status}>"
