import os
import re
import logging
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def clean_phone_number(phone: str) -> str:
    """Sanitize phone number to digits only in E.164 without leading +."""
    cleaned = re.sub(r"[^\d]", "", phone)
    return cleaned


async def send_whatsapp_message(
    recipient_phone: str,
    message: str,
    meta_access_token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    api_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a free-form text message via Meta WhatsApp Cloud API."""
    token = meta_access_token or settings.META_ACCESS_TOKEN or os.getenv("META_ACCESS_TOKEN")
    p_id = phone_number_id or settings.PHONE_NUMBER_ID or os.getenv("PHONE_NUMBER_ID")
    ver = api_version or settings.GRAPH_API_VERSION or os.getenv("GRAPH_API_VERSION", "v26.0")

    if not token or not p_id:
        raise ValueError("META_ACCESS_TOKEN and PHONE_NUMBER_ID must be configured.")

    to_number = clean_phone_number(recipient_phone)
    url = f"https://graph.facebook.com/{ver}/{p_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Unescape literal backslash-n strings to real newlines for WhatsApp formatting
    formatted_body = message.replace("\\n", "\n") if message else ""

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": formatted_body,
        },
    }

    logger.info(f"Sending WhatsApp text message to {to_number}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=30.0,
        )

    if response.status_code >= 400:
        logger.error(f"WhatsApp API error ({response.status_code}): {response.text}")
        response.raise_for_status()

    return response.json()


async def send_whatsapp_template(
    recipient_phone: str,
    template_name: str = "hello_world",
    language_code: str = "en_US",
    meta_access_token: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    api_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a pre-approved template message (e.g. for opening conversation windows)."""
    token = meta_access_token or settings.META_ACCESS_TOKEN or os.getenv("META_ACCESS_TOKEN")
    p_id = phone_number_id or settings.PHONE_NUMBER_ID or os.getenv("PHONE_NUMBER_ID")
    ver = api_version or settings.GRAPH_API_VERSION or os.getenv("GRAPH_API_VERSION", "v26.0")

    if not token or not p_id:
        raise ValueError("META_ACCESS_TOKEN and PHONE_NUMBER_ID must be configured.")

    to_number = clean_phone_number(recipient_phone)
    url = f"https://graph.facebook.com/{ver}/{p_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code,
            },
        },
    }

    logger.info(f"Sending WhatsApp template '{template_name}' to {to_number}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=30.0,
        )

    if response.status_code >= 400:
        logger.error(f"WhatsApp Template API error ({response.status_code}): {response.text}")
        response.raise_for_status()

    return response.json()


class WhatsAppService:
    """WhatsApp service wrapper class for sending messages."""

    def __init__(
        self,
        meta_access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """Initialize WhatsApp service with optional credentials."""
        self.meta_access_token = meta_access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version

    async def send_text_message(
        self,
        to_phone: str,
        message: str,
    ) -> Dict[str, Any]:
        """Send a text message via WhatsApp."""
        return await send_whatsapp_message(
            recipient_phone=to_phone,
            message=message,
            meta_access_token=self.meta_access_token,
            phone_number_id=self.phone_number_id,
            api_version=self.api_version,
        )

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str = "hello_world",
        language_code: str = "en_US",
    ) -> Dict[str, Any]:
        """Send a template message via WhatsApp."""
        return await send_whatsapp_template(
            recipient_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            meta_access_token=self.meta_access_token,
            phone_number_id=self.phone_number_id,
            api_version=self.api_version,
        )
