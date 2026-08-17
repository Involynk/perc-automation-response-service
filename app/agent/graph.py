from typing import Any, TypedDict

from app.schemas.request import ResponseRequest
from app.schemas.agent import AgentState


def build_response_graph() -> Any:
    """Build and compile a LangGraph `StateGraph` that executes the Phase 5A
    node sequence: initialize -> understand -> ambiguity -> routing.

    The compiled graph is returned directly. It is still deterministic and
    uses the existing placeholder node logic. No LLMs, RAG, or tool execution
    is introduced in Phase 5A.
    """
    # Lazy import to avoid hard dependency at module import time.
    try:
        from langgraph.graph import StateGraph
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError("langgraph is required to build the compiled graph") from exc

    # Import existing node callables
    from app.agent.nodes.initialize import initialize_node
    from app.agent.nodes.understand import understand_node
    from app.agent.nodes.ambiguity import ambiguity_node
    from app.agent.nodes.routing import routing_node
    from app.agent.nodes.execution import execution_node
    from app.agent.nodes.result_check import result_check_node
    from app.agent.nodes.generation import generation_node
    from app.agent.nodes.result_validation import result_validation_node

    # Node wrappers adapt our callables to the StateGraph node signature
    def _wrap_initialize(state: dict, runtime=None) -> dict:
        # Inputs provided via compiled.invoke(inputs) populate the initial state.
        if isinstance(state, dict):
            session_id = state.get("session_id")
            message = state.get("message") or state.get("query")
        else:
            # state may already be an AgentState model instance
            session_id = getattr(state, "session_id", None)
            message = getattr(state, "message", None) or getattr(state, "query", None)

        # Call the original initialize_node with a ResponseRequest-like object
        from app.schemas.request import ResponseRequest as _RR

        req = _RR(session_id=session_id or "", message=message or "")
        created = initialize_node(req)

        # Merge incoming metadata (e.g., conversation_context) into created.metadata.
        # StateGraph may supply inputs in different shapes (raw dict, model, or
        # a wrapper with an `inputs` mapping). Be permissive when extracting
        # the caller-provided metadata so `conversation_context` is preserved.
        incoming_meta = None
        if isinstance(state, dict):
            # direct input dict or intermediate mapping
            incoming_meta = state.get("metadata") or (state.get("inputs") or {}).get("metadata")
        else:
            # model instances or wrapper objects
            incoming_meta = getattr(state, "metadata", None)
            if incoming_meta is None:
                try:
                    incoming_meta = state.get("metadata")
                except Exception:
                    # last resort: inspect an `inputs` attr
                    incoming_meta = getattr(state, "inputs", {}) and getattr(state, "inputs", {}).get("metadata")

        merged_meta = {**(created.metadata or {}), **(incoming_meta or {}), "initialized_by": "initialize_node"}

        # Return a partial state mapping matching AgentState fields
        return {
            "session_id": created.session_id,
            "query": created.query,
            "entities": created.entities.model_dump() if hasattr(created.entities, "model_dump") else created.entities,
            "ambiguity": created.ambiguity.model_dump() if hasattr(created.ambiguity, "model_dump") else created.ambiguity,
            "selected_tools": created.selected_tools.model_dump() if hasattr(created.selected_tools, "model_dump") else created.selected_tools,
            "tool_results": created.tool_results.model_dump() if hasattr(created.tool_results, "model_dump") else created.tool_results,
            "retrieved_documents": created.retrieved_documents.model_dump() if hasattr(created.retrieved_documents, "model_dump") else created.retrieved_documents,
            "metadata": merged_meta,
        }

    def _wrap_understand(state: dict, runtime=None) -> dict:
        # Reuse understand_node to set metadata flag
        from app.schemas.agent import AgentState as _AS
        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = understand_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        # Return inferred intent and entities so subsequent nodes receive them
        return {
            "metadata": {**(base_meta or {}), **(updated.metadata or {})},
            "intent": updated.intent.value if getattr(updated, "intent", None) else None,
            "secondary_intents": [s.value for s in (updated.secondary_intents or [])],
            "entities": updated.entities.model_dump() if hasattr(updated.entities, "model_dump") else updated.entities,
            "ambiguity": updated.ambiguity.model_dump() if hasattr(updated.ambiguity, "model_dump") else updated.ambiguity,
        }

    def _wrap_ambiguity(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = ambiguity_node(as_obj)
        # state may be model or dict; normalize metadata extraction
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        return {"metadata": {**(base_meta or {}), **(updated.metadata or {})}}

    def _wrap_routing(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = routing_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        return {"metadata": {**(base_meta or {}), **(updated.metadata or {})}}

    def _wrap_execution(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = execution_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        # execution_node writes to tool_results and retrieved_documents directly on the state
        return {
            "metadata": {**(base_meta or {}), **(updated.metadata or {})},
            "tool_results": updated.tool_results.model_dump() if hasattr(updated.tool_results, "model_dump") else updated.tool_results,
            "retrieved_documents": updated.retrieved_documents.model_dump() if hasattr(updated.retrieved_documents, "model_dump") else updated.retrieved_documents,
        }

    def _wrap_result_check(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = result_check_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        return {"metadata": {**(base_meta or {}), **(updated.metadata or {})}, "result_check": updated.result_check.model_dump() if hasattr(updated.result_check, "model_dump") else updated.result_check}

    def _wrap_generation(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = generation_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        return {"metadata": {**(base_meta or {}), **(updated.metadata or {})}, "draft_answer": updated.draft_answer}

    def _wrap_result_validation(state: dict, runtime=None) -> dict:
        from app.schemas.agent import AgentState as _AS

        if isinstance(state, _AS):
            as_obj = state
        else:
            as_obj = _AS.model_validate(state) if hasattr(_AS, "model_validate") else _AS(**state)
        updated = result_validation_node(as_obj)
        base_meta = state.metadata if hasattr(state, "metadata") else (state.get("metadata") or {})
        return {"metadata": {**(base_meta or {}), **(updated.metadata or {})}, "validation_result": updated.validation_result}

    class GraphInput(TypedDict, total=False):
        session_id: str
        query: str
        metadata: dict

    graph = StateGraph(state_schema=AgentState, input_schema=GraphInput, output_schema=AgentState)

    # Add nodes in sequence and compile
    graph.add_sequence([
        ("initialize", _wrap_initialize),
        ("understand", _wrap_understand),
        ("ambiguity", _wrap_ambiguity),
        ("routing", _wrap_routing),
        ("execution", _wrap_execution),
        ("result_check", _wrap_result_check),
        ("generation", _wrap_generation),
        ("result_validation", _wrap_result_validation),
    ])

    graph.set_entry_point("initialize")
    graph.set_finish_point("result_validation")

    compiled = graph.compile()

    # Attach marker for presence
    setattr(compiled, "langgraph_present", True)
    return compiled

