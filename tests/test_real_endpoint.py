import json
from fastapi.testclient import TestClient
from app.main import app

def test_real_endpoint_with_history_and_query():
    """Hits the real /api/v1/response endpoint without mocking any retrieval steps."""
    client = TestClient(app)

    payload = {
        "session_id": "lead_ee904daf-9315-4cce-a68fc3d659c8",
        "message": "Cet",
        "metadata": {
            "lead_id": "ee904daf-9315-4cce-a68fc3d659c8",
            "channel": "whatsapp",
            "conversation_history": [
                {
                    "direction": "inbound",
                    "content": "Hello, I am inquiring about Class 11 coaching batches."
                },
                {
                    "direction": "outbound",
                    "content": "Welcome to PERC! We offer 2-year integrated coaching for JEE, NEET, and CET."
                }
            ]
        }
    }

    # Hit real API endpoint
    response = client.post("/api/v1/response", json=payload)
    print("\n--- STATUS CODE ---", response.status_code)
    print("--- REAL RESPONSE JSON ---")
    print(json.dumps(response.json(), indent=2))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["answer"]) > 0
    assert data["session_id"] == "lead_ee904daf-9315-4cce-a68fc3d659c8"

if __name__ == "__main__":
    test_real_endpoint_with_history_and_query()
