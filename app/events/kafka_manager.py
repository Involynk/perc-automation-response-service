import json
import logging
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.api.v1.endpoints.response import generate_response
from app.schemas.request import ResponseRequest
from app.schemas.agent import QueryIntent
from app.services.whatsapp_service import WhatsAppService
from app.repositories.conversation_history_repository import ConversationHistoryRepository

logger = logging.getLogger(__name__)

# Fallback in case aiokafka is not installed or Kafka broker is unreachable
try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger.warning("aiokafka not installed; Kafka background listener disabled.")


class ResponseKafkaManager:
    """
    Manages asynchronous Kafka event consumption and production for response-service.
    Subscribes to:
      - perc.lead-events (from lead-capture-service)
      - perc.followup.action-required (from followup-service)
      - perc.meeting-events (from meeting-service)

    Produces to:
      - perc.response.sent (subscribers: scheduler-service, timeline-service, analytics-service)
      - perc.followup.sent (subscribers: scheduler-service, timeline-service, analytics-service)
      - perc.meeting.create-requested (subscribers: meeting-service)
    """

    def __init__(self):
        self.producer: Optional[Any] = None
        self.consumer: Optional[Any] = None
        self.consumer_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        if not KAFKA_AVAILABLE:
            logger.info("Kafka package not available. Skipping Kafka manager startup.")
            return

        bootstrap_servers = settings.KAFKA_BROKERS or settings.KAFKA_BOOTSTRAP_SERVERS

        # Additional security options for Cloud Kafka (e.g. Confluent Cloud, Upstash, AWS MSK)
        kafka_kwargs: Dict[str, Any] = {}
        if settings.KAFKA_USE_SSL or (settings.KAFKA_SASL_MECHANISM and settings.KAFKA_SASL_USERNAME):
            kafka_kwargs["security_protocol"] = "SASL_SSL" if settings.KAFKA_USE_SSL else "SASL_PLAINTEXT"
            if settings.KAFKA_SASL_MECHANISM:
                kafka_kwargs["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
            if settings.KAFKA_SASL_USERNAME:
                kafka_kwargs["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
            if settings.KAFKA_SASL_PASSWORD:
                kafka_kwargs["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                **kafka_kwargs,
            )
            await self.producer.start()
            logger.info(f"Kafka Producer started successfully on {bootstrap_servers}")

            self.consumer = AIOKafkaConsumer(
                settings.KAFKA_TOPIC_LEAD_EVENTS,
                settings.KAFKA_TOPIC_ACTION_REQUIRED,
                settings.KAFKA_TOPIC_MEETING_EVENTS,
                bootstrap_servers=bootstrap_servers,
                group_id=settings.KAFKA_GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                **kafka_kwargs,
            )
            await self.consumer.start()
            self.is_running = True
            logger.info(f"Kafka Consumer subscribed to topics on {bootstrap_servers}")

            self.consumer_task = asyncio.create_task(self._consume_loop())
        except Exception as e:
            logger.warning(f"Failed to start Kafka Manager (Broker may be offline): {e}")

    async def stop(self):
        self.is_running = False
        if self.consumer_task:
            self.consumer_task.cancel()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Kafka Manager stopped gracefully.")

    async def publish_response_sent(
        self,
        lead_id: str,
        channel: str = "whatsapp",
        response_type: str = "general_reply",
        correlation_id: Optional[str] = None,
    ):
        if not self.producer:
            logger.debug("Producer offline; skipping perc.response.sent publish")
            return
        payload = {
            "eventId": f"evt_resp_{int(datetime.utcnow().timestamp() * 1000)}",
            "leadId": lead_id,
            "correlationId": correlation_id or lead_id,
            "responseType": response_type,
            "channel": channel,
            "sentAt": datetime.utcnow().isoformat() + "Z",
        }
        await self.producer.send_and_wait(
            settings.KAFKA_TOPIC_RESPONSE_SENT, key=lead_id, value=payload
        )
        logger.info(f"Emitted perc.response.sent for lead {lead_id}")

    async def publish_followup_sent(self, lead_id: str, channel: str = "whatsapp"):
        if not self.producer:
            logger.debug("Producer offline; skipping perc.followup.sent publish")
            return
        payload = {
            "eventId": f"evt_fu_{int(datetime.utcnow().timestamp() * 1000)}",
            "leadId": lead_id,
            "channel": channel,
            "sentAt": datetime.utcnow().isoformat() + "Z",
        }
        await self.producer.send_and_wait(
            settings.KAFKA_TOPIC_FOLLOWUP_SENT, key=lead_id, value=payload
        )
        logger.info(f"Emitted perc.followup.sent for lead {lead_id}")

    async def publish_meeting_create_requested(
        self, lead_id: str, requested_by_message: str, channel: str = "whatsapp"
    ):
        if not self.producer:
            logger.debug("Producer offline; skipping perc.meeting.create-requested publish")
            return
        payload = {
            "eventId": f"evt_meet_req_{int(datetime.utcnow().timestamp() * 1000)}",
            "leadId": lead_id,
            "channel": channel,
            "requestedByMessage": requested_by_message,
            "requestedAt": datetime.utcnow().isoformat() + "Z",
        }
        await self.producer.send_and_wait(
            settings.KAFKA_TOPIC_MEETING_CREATE_REQUESTED, key=lead_id, value=payload
        )
        logger.info(f"Emitted perc.meeting.create-requested for lead {lead_id}")

    async def _consume_loop(self):
        try:
            async for msg in self.consumer:
                topic = msg.topic
                payload = msg.value
                logger.info(f"Received Kafka event on [{topic}]: {payload.get('eventId', 'N/A')}")
                try:
                    if topic == settings.KAFKA_TOPIC_LEAD_EVENTS:
                        await self._handle_lead_event(payload)
                    elif topic == settings.KAFKA_TOPIC_ACTION_REQUIRED:
                        await self._handle_followup_action_required(payload)
                    elif topic == settings.KAFKA_TOPIC_MEETING_EVENTS:
                        await self._handle_meeting_event(payload)
                except Exception as exc:
                    logger.error(f"Error handling message on {topic}: {exc}", exc_info=True)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Kafka consume loop error: {e}", exc_info=True)

    async def _handle_lead_event(self, payload: Dict[str, Any]):
        lead_id = payload.get("leadId")
        is_new_lead = payload.get("isNewLead", False)
        channel = payload.get("channel", "whatsapp")
        history = payload.get("conversationHistory") or []

        # Extract latest message text
        latest_message = ""
        if history:
            last = history[-1]
            if isinstance(last, dict):
                content = last.get("content")
                if isinstance(content, dict):
                    latest_message = content.get("text") or content.get("body", "")
                elif isinstance(content, str):
                    latest_message = content
            elif isinstance(last, str):
                latest_message = last

        if not latest_message:
            latest_message = "Hello, I am interested in PERC courses."

        db = SessionLocal()
        try:
            req = ResponseRequest(
                session_id=f"lead_{lead_id}",
                message=latest_message,
                metadata={"lead_id": lead_id, "channel": channel, "is_new_lead": is_new_lead},
            )
            # Run AI pipeline
            res = generate_response(req, db=db)

            # Check if meeting booking intent was detected
            meeting_keywords = ["book", "schedule", "meeting", "demo", "call", "appointment", "slot"]
            has_meeting_intent = any(kw in latest_message.lower() for kw in meeting_keywords)
            if has_meeting_intent:
                await self.publish_meeting_create_requested(
                    lead_id=lead_id, requested_by_message=latest_message, channel=channel
                )
                return

            # Store both inbound message (if new) and outbound reply into centralized conversation history
            repo = ConversationHistoryRepository(db)
            phone = lead_id.replace("lead_", "").replace("whatsapp_", "")

            # Record inbound message in history
            repo.add_message(
                lead_id=lead_id,
                direction="inbound",
                message_body=latest_message,
                sender_phone=phone,
                recipient_phone="PERC_SYSTEM",
                status="RECEIVED",
            )

            # Deliver response via WhatsApp if Meta Cloud API configured
            if settings.PHONE_NUMBER_ID and settings.META_ACCESS_TOKEN:
                ws = WhatsAppService()
                ws.send_text_message(to_phone=phone, message=res.answer)

            # Record outbound AI response in history with proper sequence number
            repo.add_message(
                lead_id=lead_id,
                direction="outbound",
                message_body=res.answer,
                sender_phone="PERC_SYSTEM",
                recipient_phone=phone,
                status="SENT",
                intent=str(res.intent) if res.intent else None,
            )

            # Emit response.sent event to trigger scheduler-service, timeline-service, analytics-service
            resp_type = "welcome" if is_new_lead else "general_reply"
            await self.publish_response_sent(
                lead_id=lead_id, channel=channel, response_type=resp_type
            )
        finally:
            db.close()

    async def _handle_followup_action_required(self, payload: Dict[str, Any]):
        lead_id = payload.get("leadId")
        channel = payload.get("channel", "whatsapp")

        db = SessionLocal()
        try:
            req = ResponseRequest(
                session_id=f"lead_{lead_id}",
                message="Send follow-up re-engagement information regarding PERC programs.",
                metadata={"lead_id": lead_id, "channel": channel, "is_followup": True},
            )
            res = generate_response(req, db=db)
            phone = lead_id.replace("lead_", "").replace("whatsapp_", "")

            if settings.PHONE_NUMBER_ID and settings.META_ACCESS_TOKEN:
                ws = WhatsAppService()
                ws.send_text_message(to_phone=phone, message=res.answer)

            repo = ConversationHistoryRepository(db)
            repo.add_message(
                lead_id=lead_id,
                direction="outbound",
                message_body=res.answer,
                sender_phone="PERC_SYSTEM",
                recipient_phone=phone,
                status="SENT",
                intent=str(res.intent) if res.intent else "C12_FOLLOW_UP_CONTEXTUAL",
            )

            await self.publish_followup_sent(lead_id=lead_id, channel=channel)
        finally:
            db.close()

    async def _handle_meeting_event(self, payload: Dict[str, Any]):
        event_type = payload.get("event") or payload.get("eventType")
        if event_type != "meeting.booked":
            return

        lead_id = payload.get("leadId")
        meeting_link = payload.get("meetingLink", "https://meet.google.com/perc-demo")
        scheduled_at = payload.get("scheduledAt", "upcoming slot")
        channel = payload.get("channel", "whatsapp")

        confirmation_msg = (
            f"🎉 Your PERC Counseling Meeting is confirmed!\n\n"
            f"📅 Scheduled Time: {scheduled_at}\n"
            f"🔗 Meeting Link: {meeting_link}\n\n"
            f"Our academic advisor looks forward to speaking with you!"
        )

        db = SessionLocal()
        try:
            phone = lead_id.replace("lead_", "").replace("whatsapp_", "")
            if settings.PHONE_NUMBER_ID and settings.META_ACCESS_TOKEN:
                ws = WhatsAppService()
                ws.send_text_message(to_phone=phone, message=confirmation_msg)

            repo = ConversationHistoryRepository(db)
            repo.add_message(
                lead_id=lead_id,
                direction="outbound",
                message_body=confirmation_msg,
                sender_phone="PERC_SYSTEM",
                recipient_phone=phone,
                status="SENT",
                intent="MEETING_CONFIRMATION",
            )

            await self.publish_response_sent(
                lead_id=lead_id, channel=channel, response_type="meeting_confirmation"
            )
        finally:
            db.close()


kafka_manager = ResponseKafkaManager()
