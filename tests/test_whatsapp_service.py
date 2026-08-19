import hashlib
import hmac
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_whatsapp_repo
from app.core.config import settings
from app.services.whatsapp_service import clean_phone_number, send_whatsapp_message, send_whatsapp_template

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


def _compute_meta_signature(secret: str, body_bytes: bytes) -> str:
    """Helper to compute valid X-Hub-Signature-256 header."""
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def test_clean_phone_number():
    assert clean_phone_number("+91 93800 19642") == "919380019642"
    assert clean_phone_number("+1 (555) 123-4567") == "15551234567"
    assert clean_phone_number("919380019642") == "919380019642"


@pytest.mark.asyncio
async def test_send_whatsapp_message_mock():
    mock_resp = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "919380019642", "wa_id": "919380019642"}],
        "messages": [{"id": "wamid.mock123"}],
    }
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: mock_resp
        mock_post.return_value = mock_response

        res = await send_whatsapp_message(
            recipient_phone="+91 93800 19642",
            message="Test message",
            meta_access_token="fake_token",
            phone_number_id="fake_phone_id",
        )
        assert res["messages"][0]["id"] == "wamid.mock123"


@pytest.mark.asyncio
async def test_send_whatsapp_template_mock():
    mock_resp = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "919380019642", "wa_id": "919380019642"}],
        "messages": [{"id": "wamid.mock_template"}],
    }
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: mock_resp
        mock_post.return_value = mock_response

        res = await send_whatsapp_template(
            recipient_phone="+91 93800 19642",
            template_name="hello_world",
            meta_access_token="fake_token",
            phone_number_id="fake_phone_id",
        )
        assert res["messages"][0]["id"] == "wamid.mock_template"


def test_whatsapp_endpoints():
    mock_meta_resp = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "919380019642", "wa_id": "919380019642"}],
        "messages": [{"id": "wamid.test_endpoint"}],
    }

    with patch("app.api.v1.endpoints.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = mock_meta_resp

        # Test POST /responses/send-whatsapp
        resp = client.post(
            "/responses/send-whatsapp",
            json={"phone": "919380019642", "message": "Test via endpoint"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["meta_response"]["messages"][0]["id"] == "wamid.test_endpoint"


def test_webhook_verification():
    # Test valid challenge
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "perc_webhook_secret_token",
            "hub.challenge": "1158201444",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "1158201444"

    # Test invalid token
    resp_invalid = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "1158201444",
        },
    )
    assert resp_invalid.status_code == 403


def test_webhook_signature_verification():
    test_secret = "test_meta_app_secret_12345"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2183338108891195",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "918971392730", "phone_number_id": "1306461669211523"},
                            "statuses": [{"id": "wamid.sig_test", "status": "delivered", "timestamp": "1724050000", "recipient_id": "919380019642"}],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    with patch.object(settings, "META_APP_SECRET", test_secret):
        # 1. Valid signature -> 200 OK
        valid_sig = _compute_meta_signature(test_secret, body_bytes)
        resp_valid = client.post("/webhook", content=body_bytes, headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig})
        assert resp_valid.status_code == 200

        # 2. Invalid signature -> 403 Forbidden
        resp_invalid = client.post("/webhook", content=body_bytes, headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalid_hex_digest"})
        assert resp_invalid.status_code == 403

        # 3. Missing signature -> 403 Forbidden
        resp_missing = client.post("/webhook", content=body_bytes, headers={"Content-Type": "application/json"})
        assert resp_missing.status_code == 403


def test_webhook_malformed_payload():
    # Malformed JSON
    resp_malformed = client.post(
        "/webhook",
        content=b"not a valid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp_malformed.status_code in (400, 422)

    # Invalid Pydantic schema structure
    invalid_schema = json.dumps({"object": "whatsapp_business_account", "entry": "invalid_entry_type"}).encode("utf-8")
    resp_invalid_schema = client.post(
        "/webhook",
        content=invalid_schema,
        headers={"Content-Type": "application/json"},
    )
    assert resp_invalid_schema.status_code == 422


def test_webhook_first_wamid_and_duplicate_wamid_idempotency():
    """Test that the first wamid is processed and a duplicate wamid is skipped without re-running graph."""
    wamid_unique = f"wamid.idempotency_test_{uuid.uuid4().hex}"
    payload_incoming = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2183338108891195",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "918971392730", "phone_number_id": "1306461669211523"},
                            "contacts": [{"profile": {"name": "Abhi"}, "wa_id": "919380019642"}],
                            "messages": [
                                {
                                    "from": "919380019642",
                                    "id": wamid_unique,
                                    "timestamp": "1724050100",
                                    "type": "text",
                                    "text": {"body": "Hi, What does PERC offer?"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    with patch("app.api.v1.endpoints.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"messaging_product": "whatsapp", "messages": [{"id": "wamid.outgoing_reply"}]}

        # 1. First execution -> Processes message and calls send_whatsapp_message
        resp1 = client.post("/webhook", json=payload_incoming)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["processed_count"] == 1
        assert data1["processed_messages"][0]["status"] == "processed"
        assert mock_send.call_count == 1

        # 2. Duplicate execution -> Skips graph & sending, returns 200 OK with duplicate_skipped
        resp2 = client.post("/webhook", json=payload_incoming)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["processed_count"] == 1
        assert data2["processed_messages"][0]["status"] == "duplicate_skipped"
        assert mock_send.call_count == 1  # Not called again


def test_webhook_unsupported_message_type_safe_handling():
    """Test that unsupported message types (image, reaction, sticker) are handled safely without crashing."""
    unique_wamid = f"wamid.unsupported_image_{uuid.uuid4().hex}"
    payload_image = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2183338108891195",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "918971392730", "phone_number_id": "1306461669211523"},
                            "contacts": [{"profile": {"name": "Abhi"}, "wa_id": "919380019642"}],
                            "messages": [
                                {
                                    "from": "919380019642",
                                    "id": unique_wamid,
                                    "timestamp": "1724050200",
                                    "type": "image",
                                    "image": {"id": "media123", "mime_type": "image/jpeg"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    resp = client.post("/webhook", json=payload_image)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "received"
    assert data["processed_count"] == 1
    assert data["processed_messages"][0]["status"] == "unsupported_type"
    assert data["processed_messages"][0]["message_type"] == "image"
