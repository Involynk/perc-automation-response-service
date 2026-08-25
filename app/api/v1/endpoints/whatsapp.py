import json
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
import httpx

from app.api.deps import (
    get_response_graph,
    get_conversation_history_repo,
    verify_internal_api_key,
    verify_meta_signature,
)
from app.api.v1.endpoints.response import generate_response
from app.core.config import settings
from app.repositories.conversation_history_repository import ConversationHistoryRepository
from app.schemas.request import ResponseRequest
from app.schemas.whatsapp_webhook import MetaWebhookPayload
from app.services.whatsapp_service import clean_phone_number, send_whatsapp_message, send_whatsapp_template

logger = logging.getLogger(__name__)

router = APIRouter()


class WhatsAppRequest(BaseModel):
    phone: str = Field(..., description="Recipient phone number with country code (e.g. 919380019642)")
    message: str = Field(..., description="Text message content to send")
    lead_id: Optional[str] = Field(default=None, description="Optional lead identifier")
    is_followup: bool = Field(default=False, description="Flag indicating if this outbound message is a follow-up")


class WhatsAppTemplateRequest(BaseModel):
    phone: str = Field(..., description="Recipient phone number with country code (e.g. 919380019642)")
    template_name: str = Field(default="hello_world", description="Approved WhatsApp template name")
    language_code: str = Field(default="en_US", description="Template language code")
    lead_id: Optional[str] = Field(default=None, description="Optional lead identifier")


@router.post(
    "/responses/send-whatsapp",
    tags=["whatsapp"],
    dependencies=[Depends(verify_internal_api_key)],
)
@router.post(
    "/send-whatsapp",
    tags=["whatsapp"],
    dependencies=[Depends(verify_internal_api_key)],
)
async def send_response_whatsapp(
    request: WhatsAppRequest,
) -> Dict[str, Any]:
    """Send a direct WhatsApp message to lead/student."""
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
        logger.error(f"Meta Graph API error ({exc.response.status_code}): {exc.response.text}")
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


@router.post(
    "/responses/send-whatsapp-template",
    tags=["whatsapp"],
    dependencies=[Depends(verify_internal_api_key)],
)
@router.post(
    "/send-whatsapp-template",
    tags=["whatsapp"],
    dependencies=[Depends(verify_internal_api_key)],
)
async def send_response_whatsapp_template(
    request: WhatsAppTemplateRequest,
) -> Dict[str, Any]:
    """Send a WhatsApp pre-approved template message."""
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
        logger.error(f"Meta Graph Template API error ({exc.response.status_code}): {exc.response.text}")
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
    expected_token = settings.WEBHOOK_VERIFY_TOKEN or os.getenv("WEBHOOK_VERIFY_TOKEN", "perc_webhook_secret_token")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("✅ Meta Webhook verification challenge successful.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("❌ Webhook verification failed: Invalid verify token or mode.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/webhook", tags=["webhook"])
async def receive_webhook(
    raw_body: bytes = Depends(verify_meta_signature),
    graph: Any = Depends(get_response_graph),
    conv_repo: ConversationHistoryRepository = Depends(get_conversation_history_repo),
) -> Dict[str, Any]:
    """
    Receive incoming Meta WhatsApp webhook events (dev / direct webhook mode).
    Enforces HMAC-SHA256 signature verification, typed payload validation,
    and durable PostgreSQL conversation history logging.
    """
    # 1. Parse and validate webhook payload using typed Pydantic models
    try:
        payload = MetaWebhookPayload.model_validate_json(raw_body)
    except ValidationError as err:
        logger.error(f"❌ Malformed WhatsApp Webhook payload: {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid webhook payload structure: {err.errors()}",
        )
    except Exception as exc:
        logger.error(f"❌ Failed to parse webhook JSON body: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body",
        )

    processed_messages: List[Dict[str, Any]] = []

    for entry in payload.entry:
        for change in entry.changes:
            value = change.value

            # 2. Process incoming customer messages
            if value.messages:
                for msg in value.messages:
                    sender = msg.from_
                    msg_type = msg.type
                    # Handle Unsupported message types gracefully
                    if msg_type != "text" or not msg.text:
                        logger.warning(
                            f"⚠️ Unsupported WhatsApp message type '{msg_type}' from {sender} (wamid={msg_id})."
                        )
                        processed_messages.append({
                            "wamid": msg_id,
                            "sender": sender,
                            "status": "unsupported_type",
                            "message_type": msg_type,
                        })
                        continue

                    # 5. Process Text Enquiry through LangGraph response pipeline
                    text_body = msg.text.body
                    logger.info(
                        f"📩 [NEW WHATSAPP ENQUIRY] From: {sender} | Body: \"{text_body}\" | ID: {msg_id}"
                    )

                    response_req = ResponseRequest(
                        session_id=f"whatsapp_{sender}",
                        message=text_body,
                        metadata={
                            "channel": "whatsapp",
                            "sender_phone": sender,
                            "whatsapp_message_id": msg_id,
                            "lead_id": sender,
                        },
                    )

                    response_res = generate_response(request=response_req, graph=graph)
                    generated_answer = response_res.answer
                    intent_str = response_res.intent.value if response_res.intent else None

                    logger.info(
                        f"🤖 Generated Answer for {sender} (intent={intent_str}, status={response_res.status}): \"{generated_answer}\""
                    )

                    # 6. Deliver generated reply to user via WhatsApp Cloud API
                    outgoing_meta_res = None
                    outbound_wamid = None
                    send_error = None
                    try:
                        outgoing_meta_res = await send_whatsapp_message(
                            recipient_phone=sender,
                            message=generated_answer,
                        )
                        if outgoing_meta_res and "messages" in outgoing_meta_res and len(outgoing_meta_res["messages"]) > 0:
                            outbound_wamid = outgoing_meta_res["messages"][0].get("id")
                        logger.info(f"🚀 Outbound WhatsApp Response Delivered to {sender}: {outgoing_meta_res}")
                    except Exception as err:
                        send_error = str(err)
                        logger.error(f"⚠️ Failed to send outbound WhatsApp reply to {sender}: {err}", exc_info=True)

                    # Store in centralized 'conversations' table
                    conv_repo.add_message(
                        lead_id=sender,
                        direction="inbound",
                        message_body=text_body,
                        wamid=msg_id,
                    )
                    conv_repo.add_message(
                        lead_id=sender,
                        direction="outbound",
                        message_body=generated_answer,
                        wamid=outbound_wamid,
                        intent=intent_str,
                    )

                    processed_messages.append({
                        "wamid": msg_id,
                        "sender": sender,
                        "status": "processed",
                        "enquiry": text_body,
                        "intent": intent_str,
                        "response_status": response_res.status,
                        "generated_answer": generated_answer,
                        "outbound_wamid": outbound_wamid,
                        "outbound_whatsapp_response": outgoing_meta_res,
                    })

            # 8. Process Outbound Message Delivery Status Updates
            if value.statuses:
                for st in value.statuses:
                    wamid = st.id
                    status_name = st.status
                    recipient = st.recipient_id
                    error_details = [e.model_dump() for e in st.errors] if st.errors else None
                    logger.info(
                        f"📊 [DELIVERY STATUS UPDATE] id={wamid} status={status_name} to={recipient} errors={error_details}"
                    )

    return {
        "status": "received",
        "processed_count": len(processed_messages),
        "processed_messages": processed_messages,
    }
