# Phase 5A — Agent Foundation (LangGraph skeleton)

Purpose
-------
Phase 5A establishes the orchestration foundation for the PERC Response Service agent.
It defines a simple, deterministic execution graph that accepts a `ResponseRequest`,
creates an `AgentState`, and walks a set of nodes: `initialize` -> `understand` -> `ambiguity` -> `routing`.

Why LangGraph?
----------------
LangGraph is the planned orchestration framework for future phases because it
provides a node-and-edge programming model that maps naturally to agent pipelines.
For Phase 5A we have integrated LangGraph to compile a deterministic StateGraph
implementation that preserves the intended graph shape and node responsibilities
while still using only placeholder node logic (no LLMs, RAG, or tools). The
compiled graph is produced by `build_response_graph()` in `app.agent.graph`.

Invoke input shape
------------------
The compiled graph expects a minimal input mapping that can be coerced into the
initial `AgentState`. Callers should provide at least:

- `session_id`: string — the student/session identifier
- `query`: string — the raw user message (this maps from `ResponseRequest.message`)

For example:

```python
graph = build_response_graph()
graph.invoke({"session_id": "session-xyz", "query": "What is the fee?"})
```

The compiled graph will return a final `AgentState`-compatible mapping (or model)
that contains the full `AgentState` contract (defaults for lists and nested
models are preserved).

AgentState
----------
This phase reuses the existing `AgentState` from `app.schemas.agent`. The graph
preserves all fields on `AgentState` (session_id, query, intent, entities,
ambiguity, selected_tools, tool_results, retrieved_documents, draft_answer,
validation_result, final_answer, human_escalation_required, metadata, etc.).

Graph nodes and responsibilities
--------------------------------
- `initialize`: Input is `ResponseRequest`. Creates a fresh `AgentState` with
  safe defaults and records an initialization marker in `metadata`.
- `understand`: Placeholder for future query understanding (intent/entity
  extraction). Currently sets `metadata["understanding_status"] = "not_implemented"`
  and does not fabricate intents or entities.
- `ambiguity`: Placeholder for ambiguity detection and clarification decision.
  Currently sets `metadata["ambiguity_status"] = "not_implemented"` and
  preserves the `AmbiguityCheck` structure.
- `routing`: Placeholder for routing decisions (structured tool vs RAG vs
  clarification). Currently sets `metadata["routing_status"] = "not_implemented"`
  and does not execute any tools.

What Phase 5A intentionally does NOT implement
---------------------------------------------
- No LLM calls or prompt engineering.
- No RAG retrieval or structured tool execution.
- No human escalation implementation.
- No external messaging, Redis, Kafka, or FastAPI endpoints.

How future phases will extend this graph
----------------------------------------
Phase 5B will replace the deterministic placeholders with real
LangGraph nodes that invoke LLM-based understanding, controlled ambiguity
generation, and routing logic that selects tool invocations. The node
contracts and `AgentState` shape are intentionally preserved so the migration
is incremental and low-risk.
