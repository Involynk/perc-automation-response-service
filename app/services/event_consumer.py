import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from app.api.v1.endpoints.response import generate_response
from app.core.config import settings
from app.schemas.events import (
    FollowupActionRequiredPayload,
    FollowupSentEventPayload,
    LeadEventPayload,
    MeetingCreateRequestedEventPayload,
    MeetingEventPayload,
    ResponseSentEventPayload,
)
from app.schemas.request import ResponseRequest
from app.services.event_producer import BaseEventProducer, get_event_producer_instance
from app.services.whatsapp_service import send_whatsapp_message, send_whatsapp_template

logger = logging.getLogger(__name__)

TOPIC_LEAD_EVENTS = "perc.lead-events"
TOPIC_FOLLOWUP_ACTION_REQUIRED = "perc.followup.action-required"
TOPIC_MEETING_EVENTS = "perc.meeting-events"


class EventConsumerHandler:
    """
    Handles business logic and dispatch for inbound Kafka event topics.
    Enforces eventId deduplication, routes to LangGraph and WhatsApp outbound client,
    and publishes downstream lifecycle events.
    """

    def __init__(self, producer: Optional[BaseEventProducer] = None, graph: Any = None):
        self.producer = producer or get_event_producer_instance()
        self.graph = graph
        self._processed_events: Set[str] = set()

    def is_already_processed(self, event_id: str) -> bool:
        return event_id in self._processed_events

    def mark_as_processed(self, event_id: str):
        self._processed_events.add(event_id)

    async def handle_lead_event(self, payload: LeadEventPayload) -> Dict[str, Any]:
        """
        Process perc.lead-events (from lead-capture-service).
        - isNewLead == True: Sends welcome response and analyzes lead.
        - isNewLead == False: Evaluates message with LangGraph. Emits meeting intent or conversational reply.
        """
        if self.is_already_processed(payload.eventId):
            logger.info(f"🔁 Duplicate lead event ignored: eventId={payload.eventId}")
            return {"status": "duplicate_skipped", "eventId": payload.eventId}

        lead_id = payload.leadId
        sender_phone = payload.phone
        message_text = payload.message
        is_new_lead = payload.isNewLead

        logger.info(f"📥 [CONSUMED LEAD EVENT] leadId={lead_id} isNewLead={is_new_lead} msg=\"{message_text}\"")

        # 1. New Lead: Deliver initial welcome message and emit response.sent
        if is_new_lead:
            welcome_text = (
                f"Hello {payload.name or 'there'}! Welcome to PERC (Pathfinder Educational Research Centre). "
                "How can we assist you with your academic coaching or admissions today?"
            )
            try:
                await send_whatsapp_message(recipient_phone=sender_phone, message=welcome_text)
                await self.producer.publish_response_sent(
                    ResponseSentEventPayload(
                        leadId=lead_id,
                        correlationId=lead_id,
                        responseType="welcome",
                        channel=payload.channel,
                    )
                )
            except Exception as exc:
                logger.error(f"⚠️ Failed to deliver welcome WhatsApp message to {sender_phone}: {exc}")
                raise exc

            self.mark_as_processed(payload.eventId)
            return {"status": "welcome_sent", "leadId": lead_id, "eventId": payload.eventId}

        # 2. Subsequent Lead Message: Evaluate via LangGraph pipeline
        from app.api.deps import get_response_graph
        graph_to_use = self.graph or get_response_graph()

        response_req = ResponseRequest(
            session_id=f"lead_{lead_id}",
            message=message_text,
            metadata={
                "lead_id": lead_id,
                "sender_phone": sender_phone,
                "channel": payload.channel,
                **payload.metadata,
            },
        )

        response_res = generate_response(request=response_req, graph=graph_to_use)
        generated_answer = response_res.answer
        intent_str = response_res.intent.value if response_res.intent else None

        # 3. Check for Meeting Booking Intent
        text_lower = message_text.lower()
        meeting_keywords = ("schedule", "book", "meeting", "counseling", "counselling", "appointment", "demo", "visit", "campus visit", "talk to counselor", "callback")
        has_meeting_intent = any(kw in text_lower for kw in meeting_keywords) or (payload.metadata.get("meeting_requested") is True)

        if has_meeting_intent:
            try:
                await self.producer.publish_meeting_create_requested(
                    MeetingCreateRequestedEventPayload(
                        leadId=lead_id,
                        channel=payload.channel,
                        requestedByMessage=message_text,
                    )
                )
                logger.info(f"📅 [MEETING INTENT EMITTED] for lead {lead_id}")
            except Exception as m_err:
                logger.error(f"⚠️ Failed to publish meeting.create-requested for {lead_id}: {m_err}")

        # 4. Deliver Conversational Response
        try:
            await send_whatsapp_message(recipient_phone=sender_phone, message=generated_answer)
            await self.producer.publish_response_sent(
                ResponseSentEventPayload(
                    leadId=lead_id,
                    correlationId=lead_id,
                    responseType="general_reply",
                    channel=payload.channel,
                )
            )
        except Exception as exc:
            logger.error(f"⚠️ Failed to send AI response to {sender_phone}: {exc}")
            raise exc

        self.mark_as_processed(payload.eventId)
        return {
            "status": "response_sent",
            "leadId": lead_id,
            "eventId": payload.eventId,
            "answer": generated_answer,
        }

    async def handle_followup_action_required(self, payload: FollowupActionRequiredPayload) -> Dict[str, Any]:
        """
        Process perc.followup.action-required (from followup-service).
        Delivers follow-up message and emits perc.followup.sent.
        """
        if self.is_already_processed(payload.eventId):
            logger.info(f"🔁 Duplicate followup event ignored: eventId={payload.eventId}")
            return {"status": "duplicate_skipped", "eventId": payload.eventId}

        lead_id = payload.leadId
        sender_phone = payload.phone
        msg = payload.suggestedMessage or "Hi! We're following up on your inquiry with PERC. Let us know if you have any questions about admissions or courses!"

        logger.info(f"📥 [CONSUMED FOLLOWUP ACTION] leadId={lead_id} type={payload.followupType}")

        try:
            await send_whatsapp_message(recipient_phone=sender_phone, message=msg)
            await self.producer.publish_followup_sent(
                FollowupSentEventPayload(
                    leadId=lead_id,
                    channel=payload.channel,
                )
            )
        except Exception as exc:
            logger.error(f"⚠️ Failed to deliver follow-up WhatsApp message to {sender_phone}: {exc}")
            raise exc

        self.mark_as_processed(payload.eventId)
        return {"status": "followup_sent", "leadId": lead_id, "eventId": payload.eventId}

    async def handle_meeting_event(self, payload: MeetingEventPayload) -> Dict[str, Any]:
        """
        Process perc.meeting-events (from meeting-service).
        Filter: event === 'meeting.booked'. Delivers WhatsApp confirmation with link and scheduled time.
        """
        if self.is_already_processed(payload.eventId):
            logger.info(f"🔁 Duplicate meeting event ignored: eventId={payload.eventId}")
            return {"status": "duplicate_skipped", "eventId": payload.eventId}

        if payload.event != "meeting.booked":
            logger.debug(f"Ignoring non-booking meeting event: {payload.event}")
            return {"status": "ignored_event_type", "event": payload.event}

        lead_id = payload.leadId
        sender_phone = payload.phone
        scheduled_at = payload.scheduledAt
        meeting_link = payload.meetingLink

        logger.info(f"📥 [CONSUMED MEETING BOOKED] leadId={lead_id} scheduledAt={scheduled_at}")

        confirmation_text = (
            f"🎉 Your 1-on-1 PERC Academic Counseling Session is confirmed!\n\n"
            f"📅 Scheduled Time: {scheduled_at}\n"
            f"🔗 Meeting Link: {meeting_link}\n\n"
            f"Host: {payload.hostName or 'PERC Academic Advisory Team'}\n"
            "Please join 5 minutes early. We look forward to speaking with you!"
        )

        try:
            await send_whatsapp_message(recipient_phone=sender_phone, message=confirmation_text)
            await self.producer.publish_response_sent(
                ResponseSentEventPayload(
                    leadId=lead_id,
                    correlationId=lead_id,
                    responseType="general_reply",
                    channel="whatsapp",
                )
            )
        except Exception as exc:
            logger.error(f"⚠️ Failed to deliver meeting confirmation WhatsApp message to {sender_phone}: {exc}")
            raise exc

        self.mark_as_processed(payload.eventId)
        return {"status": "meeting_confirmation_sent", "leadId": lead_id, "eventId": payload.eventId}

    async def dispatch_raw_event(self, topic: str, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch incoming parsed event dict to appropriate topic handler."""
        if topic == TOPIC_LEAD_EVENTS:
            payload = LeadEventPayload.model_validate(raw_payload)
            return await self.handle_lead_event(payload)
        elif topic == TOPIC_FOLLOWUP_ACTION_REQUIRED:
            payload = FollowupActionRequiredPayload.model_validate(raw_payload)
            return await self.handle_followup_action_required(payload)
        elif topic == TOPIC_MEETING_EVENTS:
            payload = MeetingEventPayload.model_validate(raw_payload)
            return await self.handle_meeting_event(payload)
        else:
            logger.warning(f"⚠️ Unrecognized Kafka topic received: {topic}")
            return {"status": "unknown_topic", "topic": topic}


class KafkaEventConsumerService:
    """Production background Kafka consumer worker."""

    def __init__(self, handler: Optional[EventConsumerHandler] = None):
        self.handler = handler or EventConsumerHandler()
        self.running = False
        self._consumer = None
        self._task = None

    async def start(self):
        """Start consumer loop if Kafka is configured."""
        if not settings.KAFKA_ENABLED or not settings.KAFKA_BOOTSTRAP_SERVERS:
            logger.debug("Kafka not enabled; skipping KafkaEventConsumerService startup.")
            return

        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                TOPIC_LEAD_EVENTS,
                TOPIC_FOLLOWUP_ACTION_REQUIRED,
                TOPIC_MEETING_EVENTS,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=settings.KAFKA_CONSUMER_GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                enable_auto_commit=True,
            )
            await self._consumer.start()
            self.running = True
            self._task = asyncio.create_task(self._consume_loop())
            logger.info(f"✅ Kafka consumer group '{settings.KAFKA_CONSUMER_GROUP_ID}' started on {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as exc:
            logger.error(f"❌ Failed to start Kafka consumer service: {exc}", exc_info=True)

    async def _consume_loop(self):
        """Main consumption loop with dead-letter / error isolation."""
        while self.running and self._consumer:
            try:
                async for msg in self._consumer:
                    if not self.running:
                        break
                    topic = msg.topic
                    value = msg.value
                    try:
                        await self.handler.dispatch_raw_event(topic, value)
                    except Exception as handle_err:
                        logger.error(f"❌ Error processing event from {topic} (key={msg.key}): {handle_err}", exc_info=True)
            except asyncio.CancelledError:
                break
            except Exception as poll_err:
                logger.error(f"⚠️ Kafka consumer poll error: {poll_err}. Retrying in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        """Gracefully stop Kafka consumer worker."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        logger.info("Kafka consumer worker stopped.")
