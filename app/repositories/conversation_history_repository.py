import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.db.models.conversation_history import ConversationModel

logger = logging.getLogger(__name__)


class ConversationHistoryRepository:
    """
    Repository directly querying and appending to the shared 'conversations' table used by lead-capture-service.
    Appends ordered message objects to the conversation's metadata['messages'] array.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_or_create_active_conversation(self, lead_id: str, channel: str = "whatsapp") -> ConversationModel:
        """Finds active conversation session for lead or creates a new one."""
        conv = (
            self.session.query(ConversationModel)
            .filter(ConversationModel.lead_id == lead_id, ConversationModel.status == "active")
            .first()
        )
        if not conv:
            channel_id = f"chan_{channel}" if not channel.startswith("chan_") else channel
            conv = ConversationModel(
                id=str(uuid.uuid4()),
                lead_id=lead_id,
                channel_id=channel_id,
                status="active",
                metadata_json={"messages": []},
            )
            self.session.add(conv)
            self.session.commit()
            self.session.refresh(conv)
            logger.info(f"Created new active conversation record '{conv.id}' for lead '{lead_id}'")
        return conv

    def add_message(
        self,
        lead_id: str,
        direction: str,
        message_body: str,
        channel: str = "whatsapp",
        content_type: str = "text",
        wamid: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Appends an inbound or outbound message to the lead's conversation history in the 'conversations' table.
        Matches the exact message schema used by lead-capture-service.
        """
        conv = self.get_or_create_active_conversation(lead_id=lead_id, channel=channel)

        # Parse existing message array from metadata
        meta = conv.metadata_json or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        existing_messages = meta.get("messages", [])
        if not isinstance(existing_messages, list):
            existing_messages = []

        # Construct new message object matching lead-capture-service schema
        new_msg = {
            "id": str(uuid.uuid4()),
            "direction": direction,  # 'inbound' or 'outbound'
            "content_type": content_type,
            "content": message_body,
            "sent_at": datetime.utcnow().isoformat() + "Z",
            "channel_message_id": wamid,
        }
        if intent:
            new_msg["intent"] = intent

        updated_history = existing_messages + [new_msg]
        meta["messages"] = updated_history

        # Update model in database
        conv.metadata_json = meta
        self.session.add(conv)
        self.session.commit()
        self.session.refresh(conv)
        logger.info(f"Appended {direction} message to 'conversations' table for lead '{lead_id}' (Total: {len(updated_history)})")
        return updated_history

    def get_conversation_history(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retrieves ordered conversation messages array for a lead from 'conversations' table."""
        conv = (
            self.session.query(ConversationModel)
            .filter(ConversationModel.lead_id == lead_id, ConversationModel.status == "active")
            .first()
        )
        if not conv or not conv.metadata_json:
            return []

        meta = conv.metadata_json
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                return []
        return meta.get("messages", [])
