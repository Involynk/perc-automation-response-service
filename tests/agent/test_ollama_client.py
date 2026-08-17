import json
import requests
import pytest

from app.agent.providers.ollama_client import OllamaLLMClient, OllamaError


class DummyResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json


def test_generate_success(monkeypatch):
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=1)

    # Mock requests.post to return a response with choices -> content -> output_text
    def fake_post(url, json=None, timeout=None):
        body = {
            "choices": [
                {"content": [{"type": "output_text", "text": "{\"primary_intent\": \"C1_COURSE_DISCOVERY\"}"} ] }
            ]
        }
        return DummyResp(status_code=200, json_data=body)

    monkeypatch.setattr("requests.post", fake_post)
    out = client.generate("prompt")
    assert isinstance(out, str)
    assert "primary_intent" in out


def test_generate_timeout(monkeypatch):
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=0.01)

    def fake_post(url, json=None, timeout=None):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(OllamaError):
        client.generate("p")


def test_generate_http_error(monkeypatch):
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=1)

    def fake_post(url, json=None, timeout=None):
        return DummyResp(status_code=500, json_data={"error": "boom"}, text="boom")

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(OllamaError):
        client.generate("p")


def test_health_check_model_present(monkeypatch):
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=1)

    def fake_get(url, timeout=None):
        return DummyResp(status_code=200, json_data=[{"name": "qwen3:8b"}])

    monkeypatch.setattr("requests.get", fake_get)
    assert client.health_check(verify_model=True) is True


def test_health_check_missing_model(monkeypatch):
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:8b", timeout=1)

    def fake_get(url, timeout=None):
        return DummyResp(status_code=200, json_data=[{"name": "other"}])

    monkeypatch.setattr("requests.get", fake_get)
    assert client.health_check(verify_model=True) is False
