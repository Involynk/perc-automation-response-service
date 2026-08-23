from __future__ import annotations

import logging
import requests
from typing import Optional
from app.core.config import settings
from .llm_query_provider import BaseLLMClient

logger = logging.getLogger(__name__)


class GroqError(Exception):
    """Raised when Groq API communication fails."""


class GroqClient(BaseLLMClient):
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY or ""
        if not self.api_key:
            raise ValueError("LLM_API_KEY is required for Groq")

        self.base_url = (base_url or settings.LLM_BASE_URL or "https://api.groq.com/openai/v1").rstrip("/")
        self.model = model or settings.LLM_MODEL or "llama-3.3-70b-versatile"
        self.timeout = timeout or settings.LLM_TIMEOUT or 30
        self.temperature = temperature if temperature is not None else float(settings.LLM_TEMPERATURE or 0.0)

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                raise GroqError("Groq rate limit exceeded. Retry later.")

            if response.status_code >= 400:
                raise GroqError(
                    f"Groq API error {response.status_code}: {response.text[:500]}"
                )

            data = response.json()
            choices = data.get("choices")

            if not choices:
                raise GroqError("Groq returned no choices.")

            content = choices[0].get("message", {}).get("content")

            if not content:
                raise GroqError("Groq returned an empty response.")

            return content

        except requests.Timeout as exc:
            raise GroqError(f"Groq request timed out after {self.timeout}s") from exc

        except requests.RequestException as exc:
            raise GroqError(f"Groq request failed: {exc}") from exc


__all__ = ["GroqClient", "GroqError"]
