import json
import pytest

from app.agent.providers.ollama_client import OllamaLLMClient
from app.agent.providers.llm_query_provider import LLMQueryProvider


class DummyResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_llmqueryprovider_with_ollama(monkeypatch):
    # Prepare a valid structured JSON string as the model output
    structured = {
        "primary_intent": "C3_FEES_PRICING",
        "secondary_intents": [],
        "entities": {"program": "NEET UG"},
        "ambiguity": {"is_ambiguous": False, "missing_information": [], "clarification_required": False, "clarification_question": None},
        "confidence": 0.9,
    }
    json_text = json.dumps(structured)

    # Mock Ollama response structure
    def fake_post(url, json=None, timeout=None):
        body = {"choices": [{"content": [{"type": "output_text", "text": json_text}] }]}
        return DummyResp(status_code=200, json_data=body)

    monkeypatch.setattr("requests.post", fake_post)

    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=5)
    provider = LLMQueryProvider(client=client)
    result = provider.analyze("How much is NEET UG?", context=None)
    assert result["primary_intent"] == "C3_FEES_PRICING"
    assert result["entities"]["program"] == "NEET UG"
