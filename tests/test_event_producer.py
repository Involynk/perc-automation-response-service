import uuid
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_event_producer, get_whatsapp_repo
from app.schemas.events import (
    FollowupSentEventPayload,
    MeetingCreateRequestedEventPayload,
    ResponseSentEventPayload,
)
from app.services.event_producer import (
    InMemoryEventProducer,
    KafkaEventProducer,
    TOPIC_FOLLOWUP_SENT,
    TOPIC_MEETING_CREATE_REQUESTED,
    TOPIC_RESPONSE_SENT,
)

client = TestClient(app)


class InMemoryWhatsAppRepo:
    def __init__(self):
        self.processed = set()
        self.records = {}

    def is_already_processed(self, wamid: str) -> bool:
        return wamid in self.processed

    def record_processed_message(self, wamid: str, sender_phone: str, message_type: str, **kwargs):
        self.processed.add(wamid)
        self.records[wamid] = {
            "wamid": wamid,
            "sender_phone": sender_phone,
            "message_type": message_type,
            **kwargs,
        }
        return None


@pytest.fixture(autouse=True)
def override_whatsapp_repo():
    repo = InMemoryWhatsAppRepo()
    app.dependency_overrides[get_whatsapp_repo] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_whatsapp_repo, None)


@pytest.mark.asyncio
async def test_in_memory_event_producer():
    producer = InMemoryEventProducer()

    # 1. Test publish_response_sent
    resp_payload = ResponseSentEventPayload(
        leadId="lead_12345",
        correlationId="lead_12345",
        responseType="general_reply",
        channel="whatsapp",
    )
    ok1 = await producer.publish_response_sent(resp_payload)
    assert ok1 is True
    assert len(producer.published_events) == 1
    assert producer.published_events[0]["topic"] == TOPIC_RESPONSE_SENT
    assert producer.published_events[0]["key"] == "lead_12345"
    assert producer.published_events[0]["payload"]["responseType"] == "general_reply"

    # 2. Test publish_followup_sent
    followup_payload = FollowupSentEventPayload(
        leadId="lead_12345",
        channel="whatsapp",
    )
    ok2 = await producer.publish_followup_sent(followup_payload)
    assert ok2 is True
    assert len(producer.published_events) == 2
    assert producer.published_events[1]["topic"] == TOPIC_FOLLOWUP_SENT
    assert producer.published_events[1]["key"] == "lead_12345"

    # 3. Test publish_meeting_create_requested
    meeting_payload = MeetingCreateRequestedEventPayload(
        leadId="lead_12345",
        channel="whatsapp",
        requestedByMessage="I want to book an admission counseling session",
    )
    ok3 = await producer.publish_meeting_create_requested(meeting_payload)
    assert ok3 is True
    assert len(producer.published_events) == 3
    assert producer.published_events[2]["topic"] == TOPIC_MEETING_CREATE_REQUESTED
    assert producer.published_events[2]["key"] == "lead_12345"
    assert producer.published_events[2]["payload"]["requestedByMessage"] == "I want to book an admission counseling session"


@pytest.mark.asyncio
async def test_kafka_event_producer_mocked():
    producer = KafkaEventProducer(bootstrap_servers="localhost:9092")
    mock_aiokafka_producer = AsyncMock()
    producer._producer = mock_aiokafka_producer

    resp_payload = ResponseSentEventPayload(
        leadId="lead_kafka_1",
        correlationId="lead_kafka_1",
        responseType="welcome",
    )
    ok = await producer.publish_response_sent(resp_payload)
    assert ok is True
    assert mock_aiokafka_producer.send_and_wait.called
    assert mock_aiokafka_producer.send_and_wait.call_args[0][0] == TOPIC_RESPONSE_SENT
    assert mock_aiokafka_producer.send_and_wait.call_args[1]["key"] == "lead_kafka_1"


@pytest.mark.asyncio
async def test_kafka_event_producer_failure_handling():
    producer = KafkaEventProducer(bootstrap_servers="localhost:9092")
    mock_aiokafka_producer = AsyncMock()
    mock_aiokafka_producer.send_and_wait.side_effect = ConnectionError("Kafka broker unavailable")
    producer._producer = mock_aiokafka_producer

    resp_payload = ResponseSentEventPayload(
        leadId="lead_kafka_err",
        correlationId="lead_kafka_err",
    )
    with pytest.raises(ConnectionError):
        await producer.publish_response_sent(resp_payload)


def test_send_whatsapp_emits_response_sent():
    producer = InMemoryEventProducer()
    app.dependency_overrides[get_event_producer] = lambda: producer

    try:
        with patch("app.api.v1.endpoints.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messaging_product": "whatsapp", "messages": [{"id": "wamid.evt_test"}]}

            resp = client.post(
                "/responses/send-whatsapp",
                json={"phone": "919380019642", "message": "Admission response"},
            )
            assert resp.status_code == 200
            assert len(producer.published_events) == 1
            assert producer.published_events[0]["topic"] == TOPIC_RESPONSE_SENT
            assert producer.published_events[0]["key"] == "919380019642"
    finally:
        app.dependency_overrides.pop(get_event_producer, None)


def test_send_whatsapp_followup_emits_followup_sent():
    producer = InMemoryEventProducer()
    app.dependency_overrides[get_event_producer] = lambda: producer

    try:
        with patch("app.api.v1.endpoints.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messaging_product": "whatsapp", "messages": [{"id": "wamid.followup_evt"}]}

            resp = client.post(
                "/responses/send-whatsapp",
                json={
                    "phone": "919380019642",
                    "message": "Hey! Following up on your NEET enquiry.",
                    "is_followup": True,
                    "lead_id": "lead_followup_99",
                },
            )
            assert resp.status_code == 200
            assert len(producer.published_events) == 1
            assert producer.published_events[0]["topic"] == TOPIC_FOLLOWUP_SENT
            assert producer.published_events[0]["key"] == "lead_followup_99"
    finally:
        app.dependency_overrides.pop(get_event_producer, None)


def test_webhook_meeting_booking_intent_emits_meeting_and_response_events():
    producer = InMemoryEventProducer()
    app.dependency_overrides[get_event_producer] = lambda: producer

    unique_wamid = f"wamid.meeting_test_{uuid.uuid4().hex}"
    payload_meeting_inquiry = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2183338108891195",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "918971392730", "phone_number_id": "1306461669211523"},
                            "contacts": [{"profile": {"name": "Priya"}, "wa_id": "919876543210"}],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": unique_wamid,
                                    "timestamp": "1724050500",
                                    "type": "text",
                                    "text": {"body": "Hi, I want to book a counseling meeting for NEET admission."},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    try:
        with patch("app.api.v1.endpoints.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"messaging_product": "whatsapp", "messages": [{"id": "wamid.reply_meeting"}]}

            resp = client.post("/webhook", json=payload_meeting_inquiry)
            assert resp.status_code == 200

            # Verify that both meeting.create.requested and response.sent events were published
            topics_emitted = [e["topic"] for e in producer.published_events]
            assert TOPIC_MEETING_CREATE_REQUESTED in topics_emitted
            assert TOPIC_RESPONSE_SENT in topics_emitted

            meeting_event = next(e for e in producer.published_events if e["topic"] == TOPIC_MEETING_CREATE_REQUESTED)
            assert meeting_event["key"] == "919876543210"
            assert "book a counseling meeting" in meeting_event["payload"]["requestedByMessage"]
    finally:
        app.dependency_overrides.pop(get_event_producer, None)
