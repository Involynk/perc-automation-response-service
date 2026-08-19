from typing import Any
from app.core.config import settings
from .query_understanding import MockDataProvider
from .llm_query_provider import LLMQueryProvider, BaseLLMClient
from .ollama_client import OllamaLLMClient
from .hybrid_provider import HybridQueryUnderstandingProvider


def get_query_understanding_provider(client: BaseLLMClient | None = None) -> Any:
    """Return the configured query understanding provider.

    - 'mock': Deterministic mock provider (unit tests / CI)
    - 'llm' or 'hybrid': Production Hybrid provider (Deterministic Fast-Path + Ollama fallback)
    """
    provider = (settings.QUERY_UNDERSTANDING_PROVIDER or "mock").lower()
    if provider == "mock" and client is None:
        return MockDataProvider()

    # For production or when LLM/hybrid is configured
    return HybridQueryUnderstandingProvider(llm_client=client)
