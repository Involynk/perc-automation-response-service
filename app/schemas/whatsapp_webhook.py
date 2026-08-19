from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WhatsAppTextMessage(BaseModel):
    body: str = Field(..., description="The text content of the message")


class WhatsAppIncomingMessage(BaseModel):
    from_: str = Field(..., alias="from", description="Sender's WhatsApp ID/phone number with country code")
    id: str = Field(..., description="Unique Meta message identifier (wamid)")
    timestamp: str = Field(..., description="Unix timestamp of when the message was sent")
    type: str = Field(..., description="Type of message: text, image, document, audio, button, interactive, etc.")
    text: Optional[WhatsAppTextMessage] = Field(default=None, description="Text object if type is text")
    image: Optional[Dict[str, Any]] = Field(default=None, description="Image object if type is image")
    interactive: Optional[Dict[str, Any]] = Field(default=None, description="Interactive object if type is interactive")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Context object if message is a reply")


class WhatsAppContactProfile(BaseModel):
    name: Optional[str] = Field(default=None, description="User's WhatsApp profile name")


class WhatsAppContact(BaseModel):
    profile: Optional[WhatsAppContactProfile] = Field(default=None, description="Contact profile information")
    wa_id: str = Field(..., description="WhatsApp user ID (phone number)")


class WhatsAppError(BaseModel):
    code: int = Field(..., description="Meta error code")
    title: Optional[str] = Field(default=None, description="Error title")
    message: Optional[str] = Field(default=None, description="Error message")
    error_data: Optional[Dict[str, Any]] = Field(default=None, description="Additional error payload details")


class WhatsAppStatus(BaseModel):
    id: str = Field(..., description="Message wamid that this status refers to")
    status: str = Field(..., description="Message status: sent, delivered, read, failed")
    timestamp: str = Field(..., description="Unix timestamp of the status update")
    recipient_id: str = Field(..., description="Recipient's phone number")
    errors: Optional[List[WhatsAppError]] = Field(default=None, description="Errors if status is failed")


class WhatsAppMetadata(BaseModel):
    display_phone_number: Optional[str] = Field(default=None, description="Business display phone number")
    phone_number_id: Optional[str] = Field(default=None, description="Business phone number ID")


class WhatsAppValue(BaseModel):
    messaging_product: str = Field(default="whatsapp", description="Messaging product name")
    metadata: Optional[WhatsAppMetadata] = Field(default=None, description="Business phone metadata")
    contacts: Optional[List[WhatsAppContact]] = Field(default=None, description="Array of contact info")
    messages: Optional[List[WhatsAppIncomingMessage]] = Field(default=None, description="Array of incoming user messages")
    statuses: Optional[List[WhatsAppStatus]] = Field(default=None, description="Array of delivery status updates")


class WhatsAppChange(BaseModel):
    field: str = Field(..., description="Webhook event field, typically 'messages'")
    value: WhatsAppValue = Field(..., description="Event payload object")


class WhatsAppEntry(BaseModel):
    id: str = Field(..., description="WhatsApp Business Account (WABA) ID")
    changes: List[WhatsAppChange] = Field(default_factory=list, description="Array of change events")


class MetaWebhookPayload(BaseModel):
    object: str = Field(default="whatsapp_business_account", description="Top level object type")
    entry: List[WhatsAppEntry] = Field(default_factory=list, description="List of WABA entries")
