import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ResponseSentEventPayload(BaseModel):
    """Payload schema for perc.response.sent event topic."""
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    leadId: str = Field(..., description="Unique lead identifier")
    correlationId: str = Field(..., description="Correlation ID matching leadId for Kafka partition key")
    responseType: Literal["general_reply", "welcome"] = Field(default="general_reply", description="Type of response delivered")
    channel: str = Field(default="whatsapp", description="Outbound delivery channel")
    sentAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 timestamp")


class FollowupSentEventPayload(BaseModel):
    """Payload schema for perc.followup.sent event topic."""
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    leadId: str = Field(..., description="Unique lead identifier")
    channel: str = Field(default="whatsapp", description="Outbound delivery channel")
    sentAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 timestamp")


class MeetingCreateRequestedEventPayload(BaseModel):
    """Payload schema for perc.meeting.create-requested event topic."""
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    leadId: str = Field(..., description="Unique lead identifier")
    channel: str = Field(default="whatsapp", description="Inbound communication channel")
    requestedByMessage: str = Field(..., description="The message content requesting a meeting or counseling session")
    requestedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 timestamp")
