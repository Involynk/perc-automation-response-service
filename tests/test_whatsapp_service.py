import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.whatsapp_service import clean_phone_number, send_whatsapp_message, send_whatsapp_template

client = TestClient(app)


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

        # Test POST /api/v1/responses/send-whatsapp
        resp_v1 = client.post(
            "/api/v1/responses/send-whatsapp",
            json={"phone": "919380019642", "message": "Test via v1 endpoint"},
        )
        assert resp_v1.status_code == 200
        assert resp_v1.json()["success"] is True


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


def test_webhook_event_post():
    # Test status update payload
    payload_status = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2183338108891195",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "918971392730", "phone_number_id": "1306461669211523"},
                            "statuses": [
                                {
                                    "id": "wamid.test",
                                    "status": "delivered",
                                    "timestamp": "1724050000",
                                    "recipient_id": "919380019642",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    resp = client.post("/webhook", json=payload_status)
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"

    # Test incoming customer message payload with full enquiry-to-response flow
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
                                    "id": "wamid.incoming123",
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

        resp_msg = client.post("/webhook", json=payload_incoming)
        assert resp_msg.status_code == 200
        data = resp_msg.json()
        assert data["status"] == "received"
        assert data["processed_count"] == 1
        processed = data["processed_messages"][0]
        assert processed["sender"] == "919380019642"
        assert processed["enquiry"] == "Hi, What does PERC offer?"
        assert len(processed["generated_answer"]) > 0
        assert mock_send.called
        assert mock_send.call_args[1]["recipient_phone"] == "919380019642"
        assert mock_send.call_args[1]["message"] == processed["generated_answer"]



