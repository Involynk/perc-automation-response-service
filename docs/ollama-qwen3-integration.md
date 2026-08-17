# Ollama + Qwen3 (Phase 5D preparation)

This document describes how the project integrates a local Ollama server
running the Qwen3 8B model with the Query Understanding pathway. This
integration is intentionally minimal: Ollama is used only as an LLM backend
for structured classification in Phase 5B; routing and execution remain
deterministic and separate.

Files
-----
- `app/agent/providers/ollama_client.py` — `OllamaLLMClient` implementing `BaseLLMClient`.
- `app/agent/providers/factory.py` — updated to construct `OllamaLLMClient` when
  `LLM_PROVIDER=ollama` and `QUERY_UNDERSTANDING_PROVIDER=llm`.

Configuration
-------------
Environment variables (see `.env.example`):
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL` (default `qwen3:8b`)
- `OLLAMA_TIMEOUT` (default `120` seconds)

How it works
------------
1. `LLMQueryProvider` constructs the prompt from `app/agent/prompts/query_understanding.py`.
2. The `OllamaLLMClient` sends a non-streaming `POST /api/generate` request to Ollama with the configured model.
3. Ollama returns a JSON payload; the client extracts the generated text.
4. `LLMQueryProvider` parses the generated text as JSON and validates against the Pydantic `QueryUnderstandingResultModel`.

Testing
-------
- Unit tests for `OllamaLLMClient` and integration tests with `LLMQueryProvider` are provided under `tests/agent/` and mock HTTP calls — they do not require a running Ollama server.

Local smoke test (optional)
---------------------------
If you run Ollama locally and have pulled `qwen3:8b`, you can run the script
`scripts/test_ollama_connection.py` (if present) to verify connectivity.

Security
--------
- Do not expose the Ollama endpoint publicly.
- Do not log prompts containing user data in production logs.

Phase boundary
--------------
This integration only enables the Query Understanding LLM backend. It does
not implement tool execution, RAG, answer generation, or response validation.
