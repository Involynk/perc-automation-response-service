# Phase 5B — Query Understanding

This document describes the Phase 5B Query Understanding subsystem implemented in the repository.

Overview
--------
Phase 5B introduces a deterministic test provider (`MockDataProvider`) and a production-ready,
pluggable LLM-backed provider (`LLMQueryProvider`). The system produces a structured
`QueryUnderstandingResult` which is validated via Pydantic and mapped into `AgentState`.

Components
----------
- `MockDataProvider` — Located at `app/agent/providers/query_understanding.py`.
  - Deterministic, rule-based provider that reads `MockData/` files and applies
    keyword and canonical-name matching rules.
  - Used for all unit tests to ensure deterministic behavior.

- `LLMQueryProvider` — Located at `app/agent/providers/llm_query_provider.py`.
  - Production provider that accepts a pluggable `BaseLLMClient` implementation.
  - Builds a structured prompt (see `app/agent/prompts/query_understanding.py`) and
    expects the LLM to return JSON only. The JSON is validated with Pydantic
    (`QueryUnderstandingResultModel`) and converted to the same dict contract used
    throughout the agent.
  - In production this can be backed by Ollama + Qwen3 8B using the `OllamaLLMClient`.
    See `app/agent/providers/ollama_client.py` and `docs/ollama-qwen3-integration.md` for details.

- Provider factory — `app/agent/providers/factory.py`.
  - `get_query_understanding_provider(client=None)` returns `MockDataProvider()`
    by default, or `LLMQueryProvider(client=client)` when `QUERY_UNDERSTANDING_PROVIDER` is set to `llm`.

Configuration
-------------
Configuration lives in `app/core/config.py` and is loaded via environment variables.

- `QUERY_UNDERSTANDING_PROVIDER` — `mock` (default) or `llm`.
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE` — optional LLM settings reserved for runtime wiring.

Prompt location
---------------
- The system prompt for the LLM is stored in `app/agent/prompts/query_understanding.py` as
  `PROMPT_TEMPLATE`. It enforces strict JSON output and the following constraints:
  - Use only intents C1..C18
  - Extract only supported entities present in the query/context
  - Detect ambiguity and populate `ambiguity` fields
  - Do not answer the student's question, do not invent facts, do not retrieve documents,
    do not execute tools, and do not generate a final response

Structured output validation
----------------------------
- `LLMQueryProvider` parses the LLM response as JSON and validates it using
  `QueryUnderstandingResultModel` (Pydantic). Validation ensures the `primary_intent`
  is a known enum value, `confidence` is in [0.0, 1.0], `ambiguity` matches the
  `AmbiguityCheck` model, and `entities` is a key/value mapping.

AgentState integration
----------------------
- The `understand_node` uses the provider factory to obtain a provider (mock by default)
  and calls `analyze(query, context)`.
- The returned dict is then mapped into the `AgentState` fields: `intent`,
  `secondary_intents`, `entities` (`ExtractedEntities`), `ambiguity` (`AmbiguityCheck`),
  and metadata (`understanding_status`, `understanding_confidence`).

Test strategy
-------------
- All unit tests use the `MockDataProvider` (deterministic) — no tests call a live LLM.
- New provider tests (see `tests/agent/test_llm_provider.py`) use a `StubClient`
  implementing `BaseLLMClient` to validate parsing and Pydantic validation behavior.
- The test dataset is `tests/agent/query_understanding_cases.json`, which remains the
  canonical evaluation set for C1..C18 behaviors.

Notes & Next Steps
------------------
- The `BaseLLMClient` abstraction exists for integrating an actual SDK (OpenAI/Azure/etc.).
  Implement a concrete client and configure `QUERY_UNDERSTANDING_PROVIDER=llm` in production.
- Keep `MockDataProvider` in CI to guarantee deterministic test outcomes.
