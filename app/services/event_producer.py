import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.events import (
    FollowupSentEventPayload,
    MeetingCreateRequestedEventPayload,
    ResponseSentEventPayload,
)

logger = logging.getLogger(__name__)

TOPIC_RESPONSE_SENT = "perc.response.sent"
TOPIC_FOLLOWUP_SENT = "perc.followup.sent"
TOPIC_MEETING_CREATE_REQUESTED = "perc.meeting.create-requested"


class BaseEventProducer(ABC):
    """Abstract base class for event publishing."""

    @abstractmethod
    async def publish_response_sent(self, payload: ResponseSentEventPayload) -> bool:
        """Publish perc.response.sent event."""
        pass

    @abstractmethod
    async def publish_followup_sent(self, payload: FollowupSentEventPayload) -> bool:
        """Publish perc.followup.sent event."""
        pass

    @abstractmethod
    async def publish_meeting_create_requested(self, payload: MeetingCreateRequestedEventPayload) -> bool:
        """Publish perc.meeting.create-requested event."""
        pass


class InMemoryEventProducer(BaseEventProducer):
    """In-memory event collector used for local testing and deterministic environments."""

    def __init__(self):
        self.published_events: List[Dict[str, Any]] = []

    async def publish_response_sent(self, payload: ResponseSentEventPayload) -> bool:
        event_dict = {
            "topic": TOPIC_RESPONSE_SENT,
            "key": payload.leadId,
            "payload": payload.model_dump(),
        }
        self.published_events.append(event_dict)
        logger.info(f"📢 [EVENT EMITTED] topic={TOPIC_RESPONSE_SENT} key={payload.leadId} eventId={payload.eventId}")
        return True

    async def publish_followup_sent(self, payload: FollowupSentEventPayload) -> bool:
        event_dict = {
            "topic": TOPIC_FOLLOWUP_SENT,
            "key": payload.leadId,
            "payload": payload.model_dump(),
        }
        self.published_events.append(event_dict)
        logger.info(f"📢 [EVENT EMITTED] topic={TOPIC_FOLLOWUP_SENT} key={payload.leadId} eventId={payload.eventId}")
        return True

    async def publish_meeting_create_requested(self, payload: MeetingCreateRequestedEventPayload) -> bool:
        event_dict = {
            "topic": TOPIC_MEETING_CREATE_REQUESTED,
            "key": payload.leadId,
            "payload": payload.model_dump(),
        }
        self.published_events.append(event_dict)
        logger.info(f"📢 [EVENT EMITTED] topic={TOPIC_MEETING_CREATE_REQUESTED} key={payload.leadId} eventId={payload.eventId}")
        return True

    def clear(self):
        self.published_events.clear()


class KafkaEventProducer(BaseEventProducer):
    """Production Kafka event producer using aiokafka."""

    def __init__(self, bootstrap_servers: str, client_id: str = "response-service-producer"):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._producer = None

    async def _get_producer(self):
        if self._producer is None:
            try:
                from aiokafka import AIOKafkaProducer
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    client_id=self.client_id,
                    key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else str(k).encode("utf-8"),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
                await self._producer.start()
            except Exception as exc:
                logger.error(f"❌ Failed to start Kafka producer on {self.bootstrap_servers}: {exc}")
                raise exc
        return self._producer

    async def _send_event(self, topic: str, key: str, value: Dict[str, Any]) -> bool:
        try:
            producer = await self._get_producer()
            await producer.send_and_wait(topic, key=key, value=value)
            logger.info(f"🚀 [KAFKA EVENT DELIVERED] topic={topic} key={key} eventId={value.get('eventId')}")
            return True
        except Exception as exc:
            logger.error(f"❌ Failed to publish Kafka event to topic {topic} (key={key}): {exc}", exc_info=True)
            raise exc

    async def publish_response_sent(self, payload: ResponseSentEventPayload) -> bool:
        return await self._send_event(
            topic=TOPIC_RESPONSE_SENT,
            key=payload.leadId,
            value=payload.model_dump(),
        )

    async def publish_followup_sent(self, payload: FollowupSentEventPayload) -> bool:
        return await self._send_event(
            topic=TOPIC_FOLLOWUP_SENT,
            key=payload.leadId,
            value=payload.model_dump(),
        )

    async def publish_meeting_create_requested(self, payload: MeetingCreateRequestedEventPayload) -> bool:
        return await self._send_event(
            topic=TOPIC_MEETING_CREATE_REQUESTED,
            key=payload.leadId,
            value=payload.model_dump(),
        )

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None


_global_producer: Optional[BaseEventProducer] = None


def get_event_producer_instance() -> BaseEventProducer:
    """Factory creating configured event producer instance."""
    global _global_producer
    if _global_producer is not None:
        return _global_producer

    if settings.KAFKA_ENABLED and settings.KAFKA_BOOTSTRAP_SERVERS:
        logger.info(f"Connecting to Kafka cluster at {settings.KAFKA_BOOTSTRAP_SERVERS}")
        _global_producer = KafkaEventProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id=settings.KAFKA_CLIENT_ID,
        )
    else:
        logger.debug("Using InMemoryEventProducer (Kafka not enabled).")
        _global_producer = InMemoryEventProducer()

    return _global_producer
