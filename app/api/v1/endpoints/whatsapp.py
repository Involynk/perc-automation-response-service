import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
import httpx

from app.core.config import settings
from app.services.whatsapp_service import send_whatsapp_message, send_whatsapp_template

logger = logging.getLogger(__name__)

router = APIRouter()


class WhatsAppRequest(BaseModel):
    phone: str = Field(..., description="Recipient phone number with country code (e.g. 919380019642)")
    message: str = Field(..., description="Text message content to send")


class WhatsAppTemplateRequest(BaseModel):
    phone: str = Field(..., description="Recipient phone number with country code (e.g. 919380019642)")
    template_name: str = Field(default="hello_world", description="Approved WhatsApp template name")
    language_code: str = Field(default="en_US", description="Template language code")


@router.post("/responses/send-whatsapp", tags=["whatsapp"])
@router.post("/send-whatsapp", tags=["whatsapp"])
async def send_response_whatsapp(request: WhatsAppRequest) -> Dict[str, Any]:
    """Send a WhatsApp message using the Meta WhatsApp Cloud API."""
    try:
        result = await send_whatsapp_message(
            recipient_phone=request.phone,
            message=request.message,
        )
        return {
            "success": True,
            "message": "WhatsApp message sent",
            "meta_response": result,
        }
    except httpx.HTTPStatusError as exc:
        logger.error(f"Meta Graph API error: {exc.response.text}")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Meta API Error: {exc.response.text}",
        )
    except Exception as exc:
        logger.error(f"WhatsApp sending failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post("/responses/send-whatsapp-template", tags=["whatsapp"])
@router.post("/send-whatsapp-template", tags=["whatsapp"])
async def send_response_whatsapp_template(request: WhatsAppTemplateRequest) -> Dict[str, Any]:
    """Send a WhatsApp pre-approved template message (useful for initiating 24h conversation window)."""
    try:
        result = await send_whatsapp_template(
            recipient_phone=request.phone,
            template_name=request.template_name,
            language_code=request.language_code,
        )
        return {
            "success": True,
            "message": "WhatsApp template sent",
            "meta_response": result,
        }
    except httpx.HTTPStatusError as exc:
        logger.error(f"Meta Graph Template API error: {exc.response.text}")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Meta API Error: {exc.response.text}",
        )
    except Exception as exc:
        logger.error(f"WhatsApp template sending failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get("/webhook", tags=["webhook"])
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta Webhook verification challenge endpoint."""
    expected_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "perc_webhook_secret_token")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info(f"✅ Meta Webhook verification challenge successful (token={hub_verify_token}).")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("❌ Webhook verification failed: Invalid verify token or mode.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/webhook", tags=["webhook"])
async def receive_webhook(request: Request) -> Dict[str, Any]:
    """Receive incoming WhatsApp messages and message status updates (sent/delivered/read/failed)."""
    try:
        body = await request.json()
        logger.info(f"📥 Incoming Meta Webhook Event: {body}")

        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # 1. Process Incoming User Messages
                messages = value.get("messages", [])
                for msg in messages:
                    sender = msg.get("from")
                    msg_type = msg.get("type")
                    msg_id = msg.get("id")
                    text_body = msg.get("text", {}).get("body") if msg_type == "text" else f"[{msg_type} message]"
                    
                    logger.info(
                        f"📩 [NEW WHATSAPP MESSAGE] From: {sender} | Type: {msg_type} | Body: \"{text_body}\" | ID: {msg_id}"
                    )

                # 2. Process Outbound Message Delivery Statuses
                statuses = value.get("statuses", [])
                for st in statuses:
                    wamid = st.get("id")
                    status_name = st.get("status")
                    recipient = st.get("recipient_id")
                    errors = st.get("errors")
                    logger.info(
                        f"📊 [DELIVERY STATUS] id={wamid} status={status_name} to={recipient} errors={errors}"
                    )

        return {"status": "received"}
    except Exception as exc:
        logger.error(f"Error handling webhook payload: {exc}", exc_info=True)
        return {"status": "error", "detail": str(exc)}
