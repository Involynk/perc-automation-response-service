import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.whatsapp_message import ProcessedWhatsAppMessageModel

logger = logging.getLogger(__name__)


class WhatsAppMessageRepository:
    """Repository for storing and querying processed WhatsApp messages."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_wamid(self, wamid: str) -> Optional[ProcessedWhatsAppMessageModel]:
        """Lookup processed message by wamid."""
        return self.session.query(ProcessedWhatsAppMessageModel).filter(
            ProcessedWhatsAppMessageModel.wamid == wamid
        ).first()

    def is_already_processed(self, wamid: str) -> bool:
        """Check if message with wamid has already been processed."""
        exists = self.session.query(
            self.session.query(ProcessedWhatsAppMessageModel).filter(
                ProcessedWhatsAppMessageModel.wamid == wamid
            ).exists()
        ).scalar()
        return bool(exists)

    def record_processed_message(
        self,
        wamid: str,
        sender_phone: str,
        message_type: str,
        message_body: Optional[str] = None,
        status: str = "PROCESSED",
        response_intent: Optional[str] = None,
        outbound_wamid: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ProcessedWhatsAppMessageModel:
        """Record or update message processing details."""
        msg = self.get_by_wamid(wamid)
        if not msg:
            msg = ProcessedWhatsAppMessageModel(
                wamid=wamid,
                sender_phone=sender_phone,
                message_type=message_type,
                message_body=message_body,
                status=status,
                response_intent=response_intent,
                outbound_wamid=outbound_wamid,
                error_message=error_message,
            )
            self.session.add(msg)
        else:
            msg.status = status
            if response_intent:
                msg.response_intent = response_intent
            if outbound_wamid:
                msg.outbound_wamid = outbound_wamid
            if error_message:
                msg.error_message = error_message

        self.session.commit()
        self.session.refresh(msg)
        return msg
