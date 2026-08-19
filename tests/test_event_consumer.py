import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.events import (
    FollowupActionRequiredPayload,
    LeadEventPayload,
    MeetingEventPayload,
)
from app.services.event_consumer import (
    EventConsumerHandler,
    KafkaEventConsumerService,
    TOPIC_FOLLOWUP_ACTION_REQUIRED,
    TOPIC_LEAD_EVENTS,
    TOPIC_MEETING_EVENTS,
)
from app.services.event_producer import (
    InMemoryEventProducer,
    TOPIC_FOLLOWUP_SENT,
    TOPIC_MEETING_CREATE_REQUESTED,
    TOPIC_RESPONSE_SENT,
)


@pytest.mark.asyncio
async def test_handle_new_lead_event():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    payload = LeadEventPayload(
        eventId="evt_new_lead_001",
        leadId="lead_101",
        isNewLead=True,
        name="Rohit",
        phone="919380019642",
        message="Hi, I am interested in NEET 2026",
    )

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.welcome1"}]}

        res = await handler.handle_lead_event(payload)
        assert res["status"] == "welcome_sent"
        assert mock_send.called
        assert "Welcome to PERC" in mock_send.call_args[1]["message"]

        # Verify response.sent event was emitted with responseType=welcome
        assert len(producer.published_events) == 1
        assert producer.published_events[0]["topic"] == TOPIC_RESPONSE_SENT
        assert producer.published_events[0]["payload"]["responseType"] == "welcome"
        assert producer.published_events[0]["key"] == "lead_101"

        # Test duplicate event handling
        dup_res = await handler.handle_lead_event(payload)
        assert dup_res["status"] == "duplicate_skipped"
        assert mock_send.call_count == 1  # Not called again


@pytest.mark.asyncio
async def test_handle_existing_lead_conversational_event():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    payload = LeadEventPayload(
        eventId="evt_lead_msg_002",
        leadId="lead_102",
        isNewLead=False,
        phone="919380019642",
        message="What is the fee structure for Class 11 NEET?",
    )

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.reply1"}]}

        res = await handler.handle_lead_event(payload)
        assert res["status"] == "response_sent"
        assert len(res["answer"]) > 0
        assert mock_send.called

        # Verify perc.response.sent event was published
        assert len(producer.published_events) == 1
        assert producer.published_events[0]["topic"] == TOPIC_RESPONSE_SENT
        assert producer.published_events[0]["key"] == "lead_102"
        assert producer.published_events[0]["payload"]["responseType"] == "general_reply"


@pytest.mark.asyncio
async def test_handle_lead_event_with_meeting_booking_intent():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    payload = LeadEventPayload(
        eventId="evt_lead_meeting_003",
        leadId="lead_103",
        isNewLead=False,
        phone="919380019642",
        message="I want to schedule an admission counseling meeting this Friday",
    )

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.reply_m"}]}

        res = await handler.handle_lead_event(payload)
        assert res["status"] == "response_sent"

        # Verify both perc.meeting.create-requested and perc.response.sent were emitted
        topics = [e["topic"] for e in producer.published_events]
        assert TOPIC_MEETING_CREATE_REQUESTED in topics
        assert TOPIC_RESPONSE_SENT in topics


@pytest.mark.asyncio
async def test_handle_followup_action_required():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    payload = FollowupActionRequiredPayload(
        eventId="evt_followup_004",
        leadId="lead_104",
        phone="919380019642",
        followupType="2h_inactivity",
        suggestedMessage="Hi! Just checking if you have any questions regarding PERC JEE batches?",
    )

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.followup1"}]}

        res = await handler.handle_followup_action_required(payload)
        assert res["status"] == "followup_sent"
        assert mock_send.called
        assert "PERC JEE batches" in mock_send.call_args[1]["message"]

        # Verify perc.followup.sent was published
        assert len(producer.published_events) == 1
        assert producer.published_events[0]["topic"] == TOPIC_FOLLOWUP_SENT
        assert producer.published_events[0]["key"] == "lead_104"

        # Duplicate event check
        dup_res = await handler.handle_followup_action_required(payload)
        assert dup_res["status"] == "duplicate_skipped"
        assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_handle_meeting_event():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    # 1. Booked meeting event -> sends confirmation and emits response.sent
    payload_booked = MeetingEventPayload(
        eventId="evt_meeting_005",
        event="meeting.booked",
        leadId="lead_105",
        phone="919380019642",
        scheduledAt="2026-08-25T11:00:00Z",
        meetingLink="https://meet.google.com/xyz-uvwx-rst",
        hostName="PERC Senior Counselor",
    )

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.meet1"}]}

        res = await handler.handle_meeting_event(payload_booked)
        assert res["status"] == "meeting_confirmation_sent"
        assert mock_send.called
        msg_body = mock_send.call_args[1]["message"]
        assert "https://meet.google.com/xyz-uvwx-rst" in msg_body
        assert "2026-08-25T11:00:00Z" in msg_body

        assert len(producer.published_events) == 1
        assert producer.published_events[0]["topic"] == TOPIC_RESPONSE_SENT

    # 2. Other meeting event -> ignored
    payload_other = MeetingEventPayload(
        eventId="evt_meeting_006",
        event="meeting.cancelled",
        leadId="lead_105",
        phone="919380019642",
        scheduledAt="2026-08-25T11:00:00Z",
        meetingLink="https://meet.google.com/xyz-uvwx-rst",
    )
    res_other = await handler.handle_meeting_event(payload_other)
    assert res_other["status"] == "ignored_event_type"


@pytest.mark.asyncio
async def test_dispatch_raw_event():
    producer = InMemoryEventProducer()
    handler = EventConsumerHandler(producer=producer)

    with patch("app.services.event_consumer.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messages": [{"id": "wamid.d1"}]}

        # Dispatch lead event
        res_lead = await handler.dispatch_raw_event(
            TOPIC_LEAD_EVENTS,
            {
                "eventId": "evt_disp_1",
                "leadId": "lead_d1",
                "isNewLead": True,
                "phone": "919380019642",
                "message": "Hi",
            },
        )
        assert res_lead["status"] == "welcome_sent"

        # Dispatch unknown topic
        res_unk = await handler.dispatch_raw_event("perc.unknown-topic", {})
        assert res_unk["status"] == "unknown_topic"


@pytest.mark.asyncio
async def test_kafka_consumer_service_lifecycle():
    consumer_service = KafkaEventConsumerService()
    # When Kafka not enabled, start is a no-op
    await consumer_service.start()
    assert consumer_service.running is False
    await consumer_service.stop()
