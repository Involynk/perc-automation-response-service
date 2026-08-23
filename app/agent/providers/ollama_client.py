import json
import logging
from typing import Any, Optional
import requests

from app.core.config import settings
from .llm_query_provider import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaLLMClient(BaseLLMClient):
    """Concrete BaseLLMClient implementation for Ollama local HTTP API.

    Optimized for fast, bounded response times with format='json', stream=False,
    and bounded num_predict.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.model = model or settings.OLLAMA_MODEL or "qwen3:8b"
        # Bounded practical timeout (default 15 seconds)
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", 15) or 15

    def _generate_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/generate"

    def generate(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # Enforce structured JSON output natively in Ollama
            "options": {
                "temperature": float(getattr(settings, "LLM_TEMPERATURE", 0.0) or 0.0),
                "num_predict": 256,  # Bounded generation tokens for fast classification/synthesis
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            logger.warning(f"Ollama request timed out after {self.timeout}s: {exc}")
            raise OllamaError(f"Ollama request timed out after {self.timeout}s: {exc}")
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Ollama connection error on {url}: {exc}")
            raise OllamaError(f"Ollama connection error: {exc}")

        if resp.status_code >= 400:
            raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except Exception as exc:
            raise OllamaError(f"Malformed Ollama JSON response: {exc}")

        try:
            if "response" in data and isinstance(data["response"], str) and data["response"].strip():
                return data["response"]

            if "thinking" in data and isinstance(data["thinking"], str) and data["thinking"].strip():
                return data["thinking"]

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

            if isinstance(data, dict) and data:
                return json.dumps(data)

            raise OllamaError("Ollama returned empty response payload")
        except Exception as exc:
            raise OllamaError(f"Failed to extract text from Ollama response: {exc}")

    def health_check(self, verify_model: bool = False) -> bool:
        """Basic health check. If verify_model=True, ensure configured model exists."""
        tags_url = self.base_url.rstrip("/") + "/api/tags"
        models_url = self.base_url.rstrip("/") + "/api/models"
        resp = None
        for url in (tags_url, models_url):
            try:
                resp = requests.get(url, timeout=min(5, self.timeout))
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
