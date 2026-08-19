from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String, func
from app.db.base import Base


class ProcessedEventModel(Base):
    """
    Tracks processed Kafka event IDs to enforce cluster-wide durable idempotency
    across multiple replica pods in production.
    """
    __tablename__ = "resp_processed_events"

    event_id = Column(String(255), primary_key=True, index=True, nullable=False)
    topic = Column(String(100), nullable=False)
    lead_id = Column(String(100), nullable=False, index=True)
    processed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProcessedEvent(event_id='{self.event_id}', topic='{self.topic}', lead_id='{self.lead_id}')>"
