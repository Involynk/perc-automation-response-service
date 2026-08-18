import json
from typing import Any, Optional

import requests

from app.core.config import settings

from .llm_query_provider import BaseLLMClient


class OllamaError(Exception):
    pass


class OllamaLLMClient(BaseLLMClient):
    """Concrete BaseLLMClient implementation for Ollama local HTTP API.

    This client performs simple non-streaming POST requests to Ollama's
    `/api/generate` endpoint using the configured model.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        if not self.base_url:
            raise ValueError("OLLAMA_BASE_URL must be configured")
        if not self.model:
            raise ValueError("OLLAMA_MODEL must be configured")

    def _generate_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/generate"

    def generate(self, prompt: str) -> str:
        url = self._generate_url()
        payload = {
            "model": self.model,
            "prompt": prompt,
            # non-streaming request
            "stream": False,
            "options": {
                "temperature": float(getattr(settings, "LLM_TEMPERATURE", 0.0) or 0.0),
                "num_predict": 2048,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise OllamaError(f"Ollama request timed out: {exc}")
        except requests.exceptions.RequestException as exc:
            raise OllamaError(f"Ollama connection error: {exc}")

        if resp.status_code >= 400:
            raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        # Attempt to parse JSON
        try:
            data = resp.json()
        except Exception as exc:
            raise OllamaError(f"Malformed Ollama JSON response: {exc}")

        # Ollama standard response field is 'response'
        try:
            if "response" in data and isinstance(data["response"], str) and data["response"].strip():
                return data["response"]

            if "thinking" in data and isinstance(data["thinking"], str) and data["thinking"].strip():
                return data["thinking"]

            # Choices -> content -> output_text fallback (OpenAI/proxy compatibility)
            choices = data.get("choices") or []
            if choices:
                first = choices[0]
                content = first.get("content") or []
                if isinstance(content, list) and content:
                    for item in content:
                        if item.get("type") == "output_text" and item.get("text") is not None:
                            return item.get("text")
                    texts = [it.get("text") for it in content if it.get("text")]
                    if texts:
                        return "".join(texts)
                if isinstance(first.get("message"), dict) and "content" in first["message"]:
                    return str(first["message"]["content"])

            if "text" in data and isinstance(data["text"], str):
                return data["text"]

            # As a last resort, serialize the JSON back to string
            return json.dumps(data)
        except Exception as exc:
            raise OllamaError(f"Failed to extract text from Ollama response: {exc}")

    def health_check(self, verify_model: bool = False) -> bool:
        """Basic health check. If verify_model=True, ensure configured model exists."""
        tags_url = self.base_url.rstrip("/") + "/api/tags"
        models_url = self.base_url.rstrip("/") + "/api/models"
        resp = None
        for url in (tags_url, models_url):
            try:
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code < 400:
                    break
            except requests.exceptions.RequestException:
                continue

        if resp is None or resp.status_code >= 400:
            return False

        if not verify_model:
            return True

        try:
            data = resp.json()
            # Ollama /api/tags returns {"models": [{"name": "qwen3:8b", ...}]}
            raw_models = data.get("models", data) if isinstance(data, dict) else data
            models = []
            if isinstance(raw_models, list):
                for entry in raw_models:
                    if isinstance(entry, dict):
                        if entry.get("name"):
                            models.append(entry["name"])
                        if entry.get("model"):
                            models.append(entry["model"])
                    elif isinstance(entry, str):
                        models.append(entry)
            target = (self.model or "").lower()
            return any(target == m.lower() or target.split(":")[0] == m.lower().split(":")[0] for m in models)
        except Exception:
            return False


__all__ = ["OllamaLLMClient", "OllamaError"]
