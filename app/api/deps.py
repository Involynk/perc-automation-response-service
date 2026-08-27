import hashlib
import hmac
import logging
from typing import Any, Generator, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agent.graph import build_response_graph
from app.core.config import settings
from app.db.session import get_db_session
from app.repositories.event_repository import ProcessedEventRepository
from app.repositories.conversation_history_repository import ConversationHistoryRepository

logger = logging.getLogger(__name__)


def get_response_graph() -> Any:
    """Dependency provider for the compiled LangGraph response graph.

    Can be overridden in tests via app.dependency_overrides[get_response_graph].
    """
    return build_response_graph()


def get_conversation_history_repo(
    db: Session = Depends(get_db_session),
) -> ConversationHistoryRepository:
    """Dependency provider for ConversationHistoryRepository."""
    return ConversationHistoryRepository(db)


def get_whatsapp_repo(
    db: Session = Depends(get_db_session),
) -> ConversationHistoryRepository:
    """Dependency provider alias for WhatsApp/Conversation repository."""
    return ConversationHistoryRepository(db)



def get_event_repo(
    db: Session = Depends(get_db_session),
) -> ProcessedEventRepository:
    """Dependency provider for ProcessedEventRepository."""
    return ProcessedEventRepository(db)


def verify_internal_api_key(
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key"),
) -> None:
    """
    Verify internal microservice authentication header.
    When INTERNAL_SERVICE_API_KEY is configured in settings:
    - Missing header raises 401 Unauthorized.
    - Invalid key raises 403 Forbidden.
    """
    expected_key = settings.INTERNAL_SERVICE_API_KEY
    if not expected_key:
        # In development/test environments where no internal key is configured, allow request
        return

    if not x_internal_api_key:
        logger.warning("Rejecting internal service request: Missing X-Internal-API-Key header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Internal-API-Key header",
        )

    if not hmac.compare_digest(expected_key, x_internal_api_key):
        logger.warning("Rejecting internal service request: Invalid X-Internal-API-Key.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Internal-API-Key",
        )


async def verify_meta_signature(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
) -> bytes:
    """
    Verify the incoming X-Hub-Signature-256 HMAC-SHA256 signature from Meta.
    Returns raw request bytes if valid.
    Raises 403 Forbidden if signature is missing or invalid when META_APP_SECRET is set.
    """
    body = await request.body()
    secret = settings.META_APP_SECRET

    if not secret:
        # If no secret is configured in dev/testing, allow requests with a warning
        logger.debug("META_APP_SECRET not configured. Skipping HMAC signature check.")
        return body

    if not x_hub_signature_256:
        logger.warning("Rejecting Meta webhook request: Missing X-Hub-Signature-256 header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Hub-Signature-256 header",
        )

    if not x_hub_signature_256.startswith("sha256="):
        logger.warning("Rejecting Meta webhook request: Malformed X-Hub-Signature-256 header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malformed X-Hub-Signature-256 header",
        )

    received_sig = x_hub_signature_256[7:]
    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_sig):
        logger.warning("Rejecting Meta webhook request: Invalid HMAC-SHA256 signature.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Hub-Signature-256 signature",
        )

    return body
