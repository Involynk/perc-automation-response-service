import json
import pytest

from app.agent.providers.llm_query_provider import LLMQueryProvider, BaseLLMClient
from app.schemas.agent import QueryIntent


class StubClient(BaseLLMClient):
    def __init__(self, response):
        self.response = response

    def generate(self, prompt: str) -> str:
        return json.dumps(self.response)


def test_llm_provider_validates_and_returns_structured():
    response = {
        "primary_intent": QueryIntent.COURSE_DETAILS.value,
        "secondary_intents": [],
        "entities": {"program": "PERC Champion"},
        "ambiguity": {"is_ambiguous": False},
        "confidence": 0.9,
    }
    client = StubClient(response)
    p = LLMQueryProvider(client=client)
    out = p.analyze("Tell me about PERC Champion", context=None)
    assert out["primary_intent"] == QueryIntent.COURSE_DETAILS.value


def test_llm_provider_malformed_output_raises():
    client = StubClient("not a json")
    p = LLMQueryProvider(client=client)
    with pytest.raises(ValueError):
        p.analyze("Hello")


def test_llm_provider_invalid_intent_raises():
    response = {
        "primary_intent": "C999_UNKNOWN",
        "secondary_intents": [],
        "entities": {},
        "ambiguity": {"is_ambiguous": False},
        "confidence": 0.5,
    }
    client = StubClient(response)
    p = LLMQueryProvider(client=client)
    with pytest.raises(ValueError):
        p.analyze("Query")


def test_llm_provider_invalid_confidence_raises():
    response = {
        "primary_intent": QueryIntent.COURSE_DISCOVERY.value,
        "secondary_intents": [],
        "entities": {},
        "ambiguity": {"is_ambiguous": False},
        "confidence": 2.0,
    }
    client = StubClient(response)
    p = LLMQueryProvider(client=client)
    with pytest.raises(ValueError):
        p.analyze("Query")
