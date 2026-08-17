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

        # Ollama may return different shapes; attempt to extract output text
        # Preferred path: choices -> content -> output_text
        try:
            # choices.content[*].text or content entries of type output_text
            choices = data.get("choices") or []
            if choices:
                # content can be a list of chunks
                first = choices[0]
                content = first.get("content") or []
                if isinstance(content, list) and content:
                    for item in content:
                        if item.get("type") == "output_text" and item.get("text") is not None:
                            return item.get("text")
                    # fallback: join any 'text' fields
                    texts = [it.get("text") for it in content if it.get("text")]
                    if texts:
                        return "".join(texts)
            # Some Ollama responses include a top-level 'text' field
            if "text" in data and isinstance(data["text"], str):
                return data["text"]

            # As a last resort, serialize the JSON back to string
            return json.dumps(data)
        except Exception as exc:
            raise OllamaError(f"Failed to extract text from Ollama response: {exc}")

    def health_check(self, verify_model: bool = False) -> bool:
        """Basic health check. If verify_model=True, ensure configured model exists."""
        models_url = self.base_url.rstrip("/") + "/api/models"
        try:
            resp = requests.get(models_url, timeout=self.timeout)
        except requests.exceptions.RequestException:
            return False
        if resp.status_code >= 400:
            return False
        if not verify_model:
            return True
        try:
            data = resp.json()
            # data expected to be a list of model dicts or names
            models = []
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and entry.get("name"):
                        models.append(entry.get("name"))
                    elif isinstance(entry, str):
                        models.append(entry)
            return self.model in models
        except Exception:
            return False


__all__ = ["OllamaLLMClient", "OllamaError"]
