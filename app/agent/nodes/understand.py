from typing import Any, Dict

from app.schemas.agent import AgentState, QueryIntent, ExtractedEntities, AmbiguityCheck
from app.agent.providers.factory import get_query_understanding_provider
from app.agent.providers.llm_query_provider import BaseLLMClient
from app.core.config import settings


def understand_node(state: AgentState) -> AgentState:
    """Phase 5B query understanding node — integrates a deterministic
    `MockDataProvider` that reads `MockData` and produces structured
    classification, entities, and ambiguity signals.

    This implementation obeys Phase 5B constraints: no LLMs, no RAG, no
    structured tool execution, and it uses MockData as the authoritative
    source of truth.
    """
    state.metadata = dict(state.metadata or {})
    # allow optional conversation context passed via state.metadata
    context = state.metadata.get("conversation_context") if isinstance(state.metadata, dict) else None

    # Select provider based on app settings. For 'llm' provider, a client must be supplied
    # by the runtime environment. For tests, the default setting is 'mock'.
    provider = None
    if settings.QUERY_UNDERSTANDING_PROVIDER.lower() == "llm":
        # In production the application should inject a configured LLM client into the factory.
        # Here we raise if none is available to avoid accidental live calls during tests.
        raise RuntimeError("LLM provider selected but no LLM client was injected. Configure the application to provide a client.")
    else:
        provider = get_query_understanding_provider()

    try:
        result = provider.analyze(state.query or "", context=context)
    except Exception as exc:
        state.metadata["understanding_status"] = "provider_error"
        state.metadata["understanding_error"] = str(exc)
        raise

    # Validate expected keys
    if not isinstance(result, dict) or "primary_intent" not in result:
        state.metadata["understanding_status"] = "malformed_provider_output"
        raise ValueError("Malformed provider output")

    pri = result["primary_intent"]
    if pri not in QueryIntent._value2member_map_:
        state.metadata["understanding_status"] = "invalid_intent"
        raise ValueError(f"Invalid intent value from provider: {pri}")

    # Attach results
    state.intent = QueryIntent(result["primary_intent"]) if result.get("primary_intent") else None
    secondary = result.get("secondary_intents") or []
    # convert secondary intent values to enums where possible
    state.secondary_intents = [QueryIntent(s) for s in secondary if s in QueryIntent._value2member_map_]

    entities = result.get("entities") or {}
    # Populate ExtractedEntities — only known fields will be set
    ee = ExtractedEntities(**entities) if isinstance(entities, dict) else ExtractedEntities()
    state.entities = ee

    ambiguity = result.get("ambiguity") or {"is_ambiguous": False}
    state.ambiguity = AmbiguityCheck(**ambiguity) if isinstance(ambiguity, dict) else AmbiguityCheck()

    # Confidence/metadata
    conf = result.get("confidence")
    if conf is None or not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
        state.metadata["understanding_status"] = "invalid_confidence"
        raise ValueError("Invalid confidence from provider")

    state.metadata["understanding_status"] = "ok"
    state.metadata["understanding_confidence"] = float(conf)

    return state
