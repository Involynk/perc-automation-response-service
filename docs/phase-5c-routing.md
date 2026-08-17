# Phase 5C — Deterministic Routing

This document describes Phase 5C: deterministic routing of interpreted queries
into execution paths (structured tools, RAG, clarification, human handoff, or safe stop).

Purpose
-------
Routing decides what should run in Phase 5D. It must be deterministic and
must not call any tools, databases, RAG, or LLMs. The router uses the
QueryIntent, secondary intents, extracted entities, and ambiguity signals
produced by Phase 5B.

Architecture
------------
- `app/agent/router.py` — pure, deterministic routing logic and Pydantic
  `RoutingDecision` model.
- `app/agent/nodes/routing.py` — LangGraph node that invokes the router and
  attaches the `routing_decision` into `AgentState.metadata`.
- `tests/agent/test_router.py` — unit tests covering C1..C18 and edge cases.

Routing model
-------------
- `RouteType`: `STRUCTURED_TOOL`, `RAG`, `CLARIFICATION`, `HUMAN_HANDOFF`, `SAFE_STOP`, `MULTI_INTENT`.
- `RoutingDecision` (Pydantic): `route`, optional `tool_name`, `reason`, `confidence`, and optional `sub_routes` for multi-intent decomposition.

Routing matrix (C1–C18)
-----------------------
- C1 COURSE_DISCOVERY -> STRUCTURED_TOOL -> `get_course_info`
- C2 COURSE_DETAILS   -> STRUCTURED_TOOL -> `get_course_info`
- C3 FEES_PRICING     -> STRUCTURED_TOOL -> `get_fee`
- C4 ELIGIBILITY      -> STRUCTURED_TOOL -> `get_eligibility`
- C5 BRANCH_LOCATION  -> STRUCTURED_TOOL -> `get_branch_info`
- C6 ADMISSION_PROCESS-> STRUCTURED_TOOL -> `get_admission_steps`
- C7 REQUIRED_DOCUMENTS -> RAG
- C8 POLICIES -> RAG
- C9 AVAILABILITY_STATUS -> STRUCTURED_TOOL -> `get_availability` (general) or `get_admission_status` (live-seat queries)
- C10 COMPARISON -> RAG
- C11 MULTI_INTENT -> MULTI_INTENT decomposition (sub_routes)
- C12 FOLLOW_UP_CONTEXTUAL -> resolved to corresponding route if context resolves; otherwise CLARIFICATION
- C13 AMBIGUOUS_INCOMPLETE -> CLARIFICATION
- C14 OUT_OF_SCOPE_ESCALATION -> SAFE_STOP
- C15 GRIEVANCE_HUMAN_HANDOFF -> HUMAN_HANDOFF
- C16 HOSTEL_ACCOMMODATION -> RAG
- C17 PLACEMENT_CAREER_OUTCOMES -> RAG
- C18 LANGUAGE_MEDIUM -> RAG

Priority order
--------------
1. Human handoff
2. Clarification / ambiguity
3. Multi-intent decomposition
4. Structured tool
5. RAG
6. Safe stop

Multi-intent handling
---------------------
When `QueryIntent.MULTI_INTENT` is detected, the router emits a
`RoutingDecision` with `route=MULTI_INTENT` and `sub_routes` listing deterministic
routes for each `secondary_intent`. Structured secondaries map to structured
tools; others map to `RAG` decisions.

Follow-up handling
------------------
If `QueryIntent.FOLLOW_UP_CONTEXTUAL` and ambiguity indicates missing context,
the router chooses `CLARIFICATION`. If context resolves to a known intent
(`secondary_intents` present), the router routes according to that intent.

Ambiguity and clarification
---------------------------
If `ambiguity.is_ambiguous` is true, the router emits a `CLARIFICATION` route
and must not select tools or RAG.

Human handoff
------------
`QueryIntent.GRIEVANCE_HUMAN_HANDOFF` always routes to `HUMAN_HANDOFF`.

Safety guarantees
-----------------
- Router is pure and deterministic; it never performs network, DB, RAG, or
  tool calls.
- The router enforces the Phase 4A authority matrix by favoring structured
  tool routes for intents that map to structured data.

Testing
-------
- Unit tests: `tests/agent/test_router.py` covers all C1..C18 routing cases,
  multi-intent decomposition, follow-up resolved/unresolved, ambiguity, and
  negative cases (missing intent, out-of-scope mapping).
- Integration tests: `tests/agent/test_graph.py` and `tests/agent/test_nodes.py`
  assert that after the LangGraph `routing` node runs, `AgentState.metadata`
  contains `routing_decision` and `routing_status`.

Phase 5D boundary
-----------------
Phase 5C stops at attaching the routing decision. Execution of tools,
RAG retrieval, LLM answer generation, or database operations happen in Phase 5D
and are outside the scope of Phase 5C.
