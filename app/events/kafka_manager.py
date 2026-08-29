import os
import json
import logging
import asyncio
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.api.deps import get_response_graph
from app.api.v1.endpoints.response import generate_response
from app.schemas.request import ResponseRequest
from app.schemas.agent import QueryIntent
from app.services.whatsapp_service import WhatsAppService
from app.repositories.conversation_history_repository import ConversationHistoryRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kafka_manager")
logger.setLevel(logging.INFO)

# Fallback in case aiokafka is not installed or Kafka broker is unreachable
try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger.warning("aiokafka not installed; Kafka background listener disabled.")


def _get_whatsapp_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Retrieve Meta WhatsApp credentials with environment variable fallbacks."""
    token = settings.META_ACCESS_TOKEN or os.getenv("META_ACCESS_TOKEN") or os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_id = settings.PHONE_NUMBER_ID or os.getenv("PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    return token, phone_id


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
            print("⚠️ [KafkaManager] aiokafka not installed. Skipping Kafka manager startup.", flush=True)
            return

        raw_servers = settings.KAFKA_BROKERS or settings.KAFKA_BOOTSTRAP_SERVERS
        if isinstance(raw_servers, str):
            raw_servers = raw_servers.strip()
            if raw_servers.startswith("[") and raw_servers.endswith("]"):
                try:
                    bootstrap_servers = json.loads(raw_servers)
                except Exception:
                    bootstrap_servers = [s.strip(" \"'") for s in raw_servers.strip("[]").split(",") if s.strip()]
            elif "," in raw_servers:
                bootstrap_servers = [s.strip() for s in raw_servers.split(",") if s.strip()]
            else:
                bootstrap_servers = raw_servers
        else:
            bootstrap_servers = raw_servers

        sasl_user = settings.KAFKA_SASL_USERNAME or os.getenv("KAFKA_SASL_USERNAME")
        sasl_pass = settings.KAFKA_SASL_PASSWORD or os.getenv("KAFKA_SASL_PASSWORD")
        sasl_mech = settings.KAFKA_SASL_MECHANISM or os.getenv("KAFKA_SASL_MECHANISM")
        use_ssl = settings.KAFKA_USE_SSL or os.getenv("KAFKA_USE_SSL", "").lower() in ("true", "1", "yes") or bool(sasl_user)

        # Security options for Cloud Kafka (Upstash, Confluent Cloud, AWS MSK)
        kafka_kwargs: Dict[str, Any] = {}
        if use_ssl or sasl_mech or sasl_user:
            kafka_kwargs["security_protocol"] = "SASL_SSL" if (use_ssl and sasl_user) else ("SSL" if use_ssl else "SASL_PLAINTEXT")
            if use_ssl:
                import ssl
                ssl_context = ssl.create_default_context()
                # DO NOT set check_hostname = False because aiokafka disables SNI server_hostname if check_hostname is False
                kafka_kwargs["ssl_context"] = ssl_context
            if sasl_mech:
                kafka_kwargs["sasl_mechanism"] = sasl_mech
            if sasl_user:
                kafka_kwargs["sasl_plain_username"] = sasl_user
            if sasl_pass:
                kafka_kwargs["sasl_plain_password"] = sasl_pass

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                api_version="auto",
                request_timeout_ms=30000,
                connections_max_idle_ms=54000,
                retry_backoff_ms=500,
                **kafka_kwargs,
            )
            await self.producer.start()
            print(f"🚀 [KafkaManager] Kafka Producer connected on {bootstrap_servers}", flush=True)

            self.consumer = AIOKafkaConsumer(
                settings.KAFKA_TOPIC_LEAD_EVENTS,
                settings.KAFKA_TOPIC_ACTION_REQUIRED,
                settings.KAFKA_TOPIC_MEETING_EVENTS,
                bootstrap_servers=bootstrap_servers,
                group_id=settings.KAFKA_GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                api_version="auto",
                session_timeout_ms=30000,
                heartbeat_interval_ms=9000,
                max_poll_interval_ms=300000,
                request_timeout_ms=30000,
                connections_max_idle_ms=54000,
                retry_backoff_ms=500,
                metadata_max_age_ms=30000,
                **kafka_kwargs,
            )
            await self.consumer.start()
            self.is_running = True
            print(f"📡 [KafkaManager] Subscribed to topics: [{settings.KAFKA_TOPIC_LEAD_EVENTS}, {settings.KAFKA_TOPIC_ACTION_REQUIRED}, {settings.KAFKA_TOPIC_MEETING_EVENTS}]", flush=True)

            self.consumer_task = asyncio.create_task(self._consume_loop())
        except Exception as e:
            print(f"⚠️ [KafkaManager] Failed to start Kafka Manager: {e}", flush=True)

    async def stop(self):
        self.is_running = False
        if self.consumer_task:
            self.consumer_task.cancel()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        print("🛑 [KafkaManager] Kafka Manager stopped.", flush=True)

    async def publish_response_sent(
        self,
        lead_id: str,
        channel: str = "whatsapp",
        response_type: str = "general_reply",
        correlation_id: Optional[str] = None,
    ):
        if not self.producer:
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
        print(f"📤 [KafkaManager] Emitted perc.response.sent for lead {lead_id}", flush=True)

    async def publish_followup_sent(self, lead_id: str, channel: str = "whatsapp"):
        if not self.producer:
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
        print(f"📤 [KafkaManager] Emitted perc.followup.sent for lead {lead_id}", flush=True)

    async def publish_meeting_create_requested(
        self, lead_id: str, requested_by_message: str, channel: str = "whatsapp"
    ):
        if not self.producer:
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
        print(f"📤 [KafkaManager] Emitted perc.meeting.create-requested for lead {lead_id}", flush=True)

    async def _consume_loop(self):
        print("🔄 [KafkaManager] Consumer loop running...", flush=True)
        try:
            async for msg in self.consumer:
                topic = msg.topic
                payload = msg.value
                print(f"📥 [KafkaManager] Received event on [{topic}]: eventId={payload.get('eventId', 'N/A')}", flush=True)
                try:
                    if topic == settings.KAFKA_TOPIC_LEAD_EVENTS:
                        await self._handle_lead_event(payload)
                    elif topic == settings.KAFKA_TOPIC_ACTION_REQUIRED:
                        await self._handle_followup_action_required(payload)
                    elif topic == settings.KAFKA_TOPIC_MEETING_EVENTS:
                        await self._handle_meeting_event(payload)
                except Exception as exc:
                    print(f"❌ [KafkaManager] Error handling message on {topic}: {exc}", flush=True)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ [KafkaManager] Consumer loop exception: {e}", flush=True)

    async def _handle_lead_event(self, payload: Dict[str, Any]):
        lead_id = payload.get("leadId")
        is_new_lead = payload.get("isNewLead", False)
        channel = payload.get("channel", "whatsapp")
        history = payload.get("conversationHistory") or []

        print(f"⚡ [KafkaManager] Processing lead event: leadId={lead_id}, isNewLead={is_new_lead}, channel={channel}", flush=True)

        # Extract latest message text from conversationHistory or direct payload fields
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
            latest_message = payload.get("message") or payload.get("text") or "Hello, I am interested in PERC courses."

        print(f"💬 [KafkaManager] Extracted inbound message: '{latest_message}'", flush=True)

        db = SessionLocal()
        try:
            req = ResponseRequest(
                session_id=f"lead_{lead_id}",
                message=latest_message,
                metadata={"lead_id": lead_id, "channel": channel, "is_new_lead": is_new_lead},
            )
            graph = get_response_graph()
            # Run AI pipeline in thread pool to prevent blocking asyncio event loop & Kafka heartbeats
            res = await asyncio.to_thread(generate_response, req, graph=graph)
            print(f"🤖 [KafkaManager] Generated response answer: '{res.answer[:80]}...'", flush=True)

            # Check if meeting booking intent was detected
            meeting_keywords = ["book", "schedule", "meeting", "demo", "call", "appointment", "slot"]
            has_meeting_intent = any(kw in latest_message.lower() for kw in meeting_keywords)
            if has_meeting_intent:
                await self.publish_meeting_create_requested(
                    lead_id=lead_id, requested_by_message=latest_message, channel=channel
                )
                return

            # Store inbound message and outbound reply into centralized conversation history
            repo = ConversationHistoryRepository(db)
            phone = payload.get("sourceReferenceId")

            if not phone:
                print(f"⚠️ [KafkaManager] sourceReferenceId missing from lead event (lead_id={lead_id})", flush=True)
                phone = ""
            else:
                phone = phone.strip()
                if not phone.startswith("+"):
                    phone = f"+{phone}"

            # Record inbound message in history
            await asyncio.to_thread(
                repo.add_message,
                lead_id=lead_id,
                direction="inbound",
                message_body=latest_message,
                channel=channel,
            )

            # Deliver response via WhatsApp if Meta Cloud API configured
            token, phone_id = _get_whatsapp_credentials()
            if token and phone_id and phone:
                try:
                    ws = WhatsAppService(meta_access_token=token, phone_number_id=phone_id)
                    await ws.send_text_message(to_phone=phone, message=res.answer)
                    print(f"✅ [KafkaManager] Outbound WhatsApp message delivered to {phone} for lead {lead_id}", flush=True)
                except Exception as wa_err:
                    print(f"❌ [KafkaManager] Failed to deliver WhatsApp message to {phone}: {wa_err}", flush=True)
            else:
                print(f"⚠️ [KafkaManager] WhatsApp credentials missing or phone invalid (phone={phone}, token_exists={bool(token)}, phone_id_exists={bool(phone_id)}). Outbound message skipped.", flush=True)

            # Record outbound AI response in history with proper sequence number
            await asyncio.to_thread(
                repo.add_message,
                lead_id=lead_id,
                direction="outbound",
                message_body=res.answer,
                channel=channel,
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
            graph = get_response_graph()
            res = await asyncio.to_thread(generate_response, req, graph=graph)
            phone = payload.get("sourceReferenceId")

            if not phone:
                raise ValueError("sourceReferenceId is missing from follow-up event")

            phone = phone.strip()
            if not phone.startswith("+"):
                phone = f"+{phone}"

            token, phone_id = _get_whatsapp_credentials()
            if token and phone_id:
                try:
                    ws = WhatsAppService(meta_access_token=token, phone_number_id=phone_id)
                    await ws.send_text_message(to_phone=phone, message=res.answer)
                    logger.info(f"✅ Outbound WhatsApp follow-up delivered to {phone}")
                except Exception as wa_err:
                    logger.error(f"❌ WhatsApp follow-up delivery failed to {phone}: {wa_err}", exc_info=True)

            repo = ConversationHistoryRepository(db)
            await asyncio.to_thread(
                repo.add_message,
                lead_id=lead_id,
                direction="outbound",
                message_body=res.answer,
                channel=channel,
                intent=str(res.intent) if res.intent else "C12_FOLLOW_UP_CONTEXTUAL",
            )

            await self.publish_response_sent(
                lead_id=lead_id, channel=channel, response_type="followup"
            )
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
            phone = payload.get("sourceReferenceId")

            if not phone:
                raise ValueError("sourceReferenceId is missing from meeting event")

            phone = phone.strip()
            if not phone.startswith("+"):
                phone = f"+{phone}"

            token, phone_id = _get_whatsapp_credentials()
            if token and phone_id:
                try:
                    ws = WhatsAppService(meta_access_token=token, phone_number_id=phone_id)
                    await ws.send_text_message(to_phone=phone, message=confirmation_msg)
                    logger.info(f"✅ Outbound WhatsApp meeting confirmation delivered to {phone}")
                except Exception as wa_err:
                    logger.error(f"❌ WhatsApp meeting confirmation delivery failed to {phone}: {wa_err}", exc_info=True)

            repo = ConversationHistoryRepository(db)
            await asyncio.to_thread(
                repo.add_message,
                lead_id=lead_id,
                direction="outbound",
                message_body=confirmation_msg,
                channel=channel,
                intent="MEETING_CONFIRMATION",
            )

            await self.publish_response_sent(
                lead_id=lead_id, channel=channel, response_type="meeting_confirmation"
            )
        finally:
            db.close()


kafka_manager = ResponseKafkaManager()

