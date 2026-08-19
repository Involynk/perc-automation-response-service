from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, func
from app.db.base import Base


class ProcessedWhatsAppMessageModel(Base):
    """
    Durable storage table for tracking processed incoming WhatsApp messages (idempotency)
    and delivery auditing.
    """
    __tablename__ = "resp_processed_whatsapp_messages"

    wamid = Column(String(255), primary_key=True, index=True, nullable=False, doc="Unique Meta message ID (wamid)")
    sender_phone = Column(String(50), nullable=False, index=True, doc="Recipient / sender phone number in international format")
    message_type = Column(String(50), nullable=False, doc="Type of message (text, image, audio, etc.)")
    message_body = Column(Text, nullable=True, doc="Received message text or payload summary")
    status = Column(String(50), nullable=False, default="PROCESSED", doc="Processing status (RECEIVED, PROCESSED, FAILED, UNSUPPORTED)")
    response_intent = Column(String(100), nullable=True, doc="Detected query intent (e.g. C1_COURSE_DISCOVERY)")
    outbound_wamid = Column(String(255), nullable=True, doc="Outbound reply Meta message ID")
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, doc="Timestamp when webhook received message")
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, doc="Timestamp when processing finished")
    error_message = Column(Text, nullable=True, doc="Error message if processing failed")

    def __repr__(self) -> str:
        return f"<ProcessedWhatsAppMessage wamid={self.wamid} sender={self.sender_phone} status={self.status}>"
