# Phase 5D — Execution Layer

This document describes the Phase 5D execution layer implemented in the
Response Service. It focuses on deterministic execution of structured tools
and RAG retrieval based on the `RoutingDecision` determined in Phase 5C.

Architecture
------------
- `app.agent.executor.ExecutionEngine`: centralized executor that runs either
  structured tools (via the `app.tools.structured` registry) or RAG retrieval
  (via `app.rag.retrieval.KnowledgeRetriever`). The engine is injectable and
  designed to be mocked in tests.
- `app.agent.nodes.execution.execution_node`: LangGraph node that delegates
  execution to the `ExecutionEngine` and records results in `AgentState`.
- `app.agent.graph.build_response_graph`: the compiled LangGraph now includes
  the `execution` node after routing. The sequence is: initialize →
  understand → ambiguity → routing → execution.

Tool registry
-------------
Only an explicit, whitelisted set of structured tools may be executed:

- `get_course_info`
- `get_fee`
- `get_branch_info`
- `get_eligibility`
- `get_admission_steps`
- `get_admission_status`
- `get_availability`

These map directly to functions in `app.tools.structured` and are invoked with
an instance of `StructuredDataService` (in production) or a test double (in
unit tests). The executor never runs arbitrary Python based on LLM output.

Structured execution
--------------------
- Parameters are constructed conservatively from `AgentState.entities`, the
  raw `query`, and `routing_decision`. No parameters are invented.
- If required parameters are missing for a tool, the executor records a
  `ToolResult` with `success=False` and `error="Missing parameters for tool execution"`.
- Tool results are appended to `AgentState.tool_results` preserving
  `tool_name`, `success`, `data`, `error`, and `metadata`.

RAG execution
-------------
- Uses the existing `KnowledgeRetriever` facade (`app.rag.retrieval.KnowledgeRetriever`).
- Respects defaults: `top_k=3`, min similarity threshold 0.70 is honored by
  the retriever where applicable.
- Retrieved documents are stored in `AgentState.retrieved_documents` as
  `RetrievedDocument` instances and also summarized in a `ToolResult` named
  `rag_search` (with `data` containing serialized retrieved documents).

Multi-intent
------------
- For `RouteType.MULTI_INTENT`, the executor runs each `sub_route` in order
  and collects results independently (structured and/or RAG). Results are not
  merged into natural language; they remain in `tool_results` and
  `retrieved_documents` for downstream processing.

Clarification / Handoff / Safe Stop
-----------------------------------
- `CLARIFICATION`: executor performs no tool/RAG execution and sets
  `metadata.execution_status = "awaiting_clarification"`.
- `HUMAN_HANDOFF`: executor sets `metadata.execution_status = "human_handoff"`
  and `state.human_escalation_required = True`.
- `SAFE_STOP`: executor sets `metadata.execution_status = "safe_stop"` and
  executes nothing.

Failure isolation and idempotency
---------------------------------
- Individual tool failures are caught and recorded as failed `ToolResult`
  entries; they do not abort the entire execution flow.
- The engine tracks executed tool keys within a single graph invocation to
  avoid duplicate executions.

Testing strategy
----------------
- The executor is designed for injection: use `app.agent.executor.set_global_execution_engine()`
  in tests to provide a fake engine with stubbed `structured_service` and
  `retriever`.
- Tests in `tests/agent/test_execution_node.py` demonstrate structured tool
  execution, RAG execution, multi-intent, clarification, human handoff, and
  safe stop behavior without a live DB or external services.

Notes and constraints
---------------------
- The execution node does not perform natural-language generation or answer
  validation — those are Phase 5E+ responsibilities.
- The node does not create raw SQL sessions; production StructuredDataService
  is used by the engine when real DB access is required, but tests should
  inject fakes to avoid DB usage.
