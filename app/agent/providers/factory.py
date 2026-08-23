from typing import Any
from .llm_query_provider import LLMQueryProvider, BaseLLMClient
from .groq_client import GroqClient


def get_query_understanding_provider(client: BaseLLMClient | None = None) -> Any:
    """Return pure LLM query understanding provider backed by Groq."""
    llm_client = client or GroqClient()
    return LLMQueryProvider(client=llm_client)
