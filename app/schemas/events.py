import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


# ==========================================
# Produced Event Schemas (Outgoing from Response Service)
# ==========================================

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


# ==========================================
# Consumed Event Schemas (Inbound to Response Service)
# ==========================================

class LeadEventPayload(BaseModel):
    """Payload schema for perc.lead-events (from lead-capture-service)."""
    eventId: str = Field(..., description="Unique event identifier")
    leadId: str = Field(..., description="Unique lead identifier")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    isNewLead: bool = Field(default=False, description="True if newly captured lead; False for subsequent message")
    name: Optional[str] = Field(default=None, description="Lead name")
    phone: str = Field(..., description="Lead phone number")
    message: str = Field(..., description="Inbound message content from lead")
    channel: str = Field(default="whatsapp", description="Communication channel")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FollowupActionRequiredPayload(BaseModel):
    """Payload schema for perc.followup.action-required (from followup-service)."""
    eventId: str = Field(..., description="Unique event identifier")
    leadId: str = Field(..., description="Unique lead identifier")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    phone: str = Field(..., description="Lead phone number")
    followupType: str = Field(default="2h_inactivity", description="Reason or stage for follow-up")
    suggestedMessage: Optional[str] = Field(default=None, description="Pre-composed or suggested follow-up text")
    channel: str = Field(default="whatsapp", description="Outbound delivery channel")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MeetingEventPayload(BaseModel):
    """Payload schema for perc.meeting-events (from meeting-service)."""
    eventId: str = Field(..., description="Unique event identifier")
    event: str = Field(default="meeting.booked", description="Meeting event type")
    leadId: str = Field(..., description="Unique lead identifier")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    phone: str = Field(..., description="Lead phone number")
    scheduledAt: str = Field(..., description="ISO 8601 scheduled meeting timestamp")
    meetingLink: str = Field(..., description="Google Meet, Jitsi, or video room URL")
    hostName: Optional[str] = Field(default=None, description="Counselor or host name")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
