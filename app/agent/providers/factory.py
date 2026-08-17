from typing import Any
from app.core.config import settings
from .query_understanding import MockDataProvider

from .llm_query_provider import LLMQueryProvider, BaseLLMClient
from .ollama_client import OllamaLLMClient


def get_query_understanding_provider(client: BaseLLMClient | None = None) -> Any:
    """Return the configured query understanding provider.

    By default the `QUERY_UNDERSTANDING_PROVIDER` setting controls which provider
    is returned. For unit tests, pass `client` or set the setting to 'mock'.
    """
    provider = (settings.QUERY_UNDERSTANDING_PROVIDER or "mock").lower()
    if provider == "mock":
        return MockDataProvider()
    if provider == "llm":
        # If a client is provided (tests), use it. Otherwise, construct based on configured LLM_PROVIDER.
        if client is not None:
            return LLMQueryProvider(client=client)

        llm_provider = (settings.LLM_PROVIDER or "").lower()
        if llm_provider == "ollama":
            # construct Ollama client using settings
            client = OllamaLLMClient()
            return LLMQueryProvider(client=client)

        raise RuntimeError("LLM client must be provided or configured (set LLM_PROVIDER=ollama and provide Ollama settings)")
    raise RuntimeError(f"Unknown QUERY_UNDERSTANDING_PROVIDER: {provider}")
