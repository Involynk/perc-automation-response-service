from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.agent import AgentState, ToolResult, RetrievedDocument
from app.agent.router import RouteType, RoutingDecision


class ExecutionEngine:
    """Centralized execution engine for Phase 5D.

    By default this engine expects to be constructed with two optional
    collaborators which are safe to mock in tests:
      - structured_service: an instance of `StructuredDataService`
      - retriever: an instance of `KnowledgeRetriever`

    If not provided, the engine will attempt to construct real services
    which may require DB access; tests should inject fakes.
    """

    def __init__(self, structured_service: Any = None, retriever: Any = None):
        self.structured_service = structured_service
        self.retriever = retriever

        # map of allowed structured tools to caller functions (imported lazily)
        from app.tools.structured import (
            get_course_info,
            get_fee,
            get_branch_info,
            get_eligibility,
            get_admission_steps,
            get_admission_status,
            get_availability,
        )

        self._tool_map = {
            "get_course_info": get_course_info,
            "get_fee": get_fee,
            "get_branch_info": get_branch_info,
            "get_eligibility": get_eligibility,
            "get_admission_steps": get_admission_steps,
            "get_admission_status": get_admission_status,
            "get_availability": get_availability,
        }

    def execute(self, state: AgentState) -> AgentState:
        state.metadata = dict(state.metadata or {})
        rd_raw = state.metadata.get("routing_decision")
        if not rd_raw:
            state.metadata["execution_status"] = "no_routing_decision"
            return state

        # Build RoutingDecision object if it's a dict
        if isinstance(rd_raw, dict):
            rd = RoutingDecision.model_validate(rd_raw) if hasattr(RoutingDecision, "model_validate") else RoutingDecision(**rd_raw)
        else:
            rd = rd_raw

        executed = set()

        def _exec_single(route: RoutingDecision):
            # idempotency key
            key = (route.route.value, route.tool_name or "", route.reason or "")
            if key in executed:
                return
            executed.add(key)

            if route.route == RouteType.STRUCTURED_TOOL:
                tool = route.tool_name
                if not tool or tool not in self._tool_map:
                    state.tool_results.append(ToolResult(tool_name=tool or "unknown", success=False, error="Unknown structured tool", metadata={}))
                    return

                # Build parameters from state.entities and query conservatively
                params = self._build_tool_params(tool, state)
                if params is None:
                    # missing required information
                    state.tool_results.append(ToolResult(tool_name=tool, success=False, error="Missing parameters for tool execution", metadata={"reason": "missing_parameters"}))
                    return

                try:
                    func = self._tool_map[tool]
                    result = func(self.structured_service, params)
                    state.tool_results.append(result)
                except Exception as exc:
                    state.tool_results.append(ToolResult(tool_name=tool, success=False, error=str(exc), metadata={}))

            elif route.route == RouteType.RAG:
                # Use retriever.search to fetch documents
                try:
                    top_k = 3
                    docs = self.retriever.search(state.query or "", top_k=top_k)
                    rd_list = [RetrievedDocument.model_validate(d.model_dump()) if hasattr(d, "model_dump") else d for d in docs]
                    state.retrieved_documents.extend(rd_list)
                    # Add a ToolResult entry summarizing the retrieval
                    state.tool_results.append(ToolResult(tool_name="rag_search", success=True, data=[d.model_dump() for d in rd_list], metadata={"count": len(rd_list)}))
                except Exception as exc:
                    state.tool_results.append(ToolResult(tool_name="rag_search", success=False, error=str(exc), metadata={}))

            elif route.route == RouteType.CLARIFICATION:
                # no execution; preserve ambiguity
                state.metadata["execution_status"] = "awaiting_clarification"
                return

            elif route.route == RouteType.HUMAN_HANDOFF:
                state.metadata["execution_status"] = "human_handoff"
                state.human_escalation_required = True
                return

            elif route.route == RouteType.SAFE_STOP:
                state.metadata["execution_status"] = "safe_stop"
                return

        # dispatch
        if rd.route == RouteType.MULTI_INTENT and rd.sub_routes:
            for sub in rd.sub_routes:
                _exec_single(sub)
        else:
            _exec_single(rd)

        # mark finished
        if "execution_status" not in state.metadata:
            state.metadata["execution_status"] = "ok"

        return state

    def _build_tool_params(self, tool: str, state: AgentState) -> Optional[Any]:
        # Conservative parameter construction: map known entity fields to tool input models
        entities = state.entities
        q = state.query

        if tool == "get_course_info":
            from app.tools.structured import CourseInfoToolInput
            return CourseInfoToolInput(course_name=entities.course, course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None, target_class=entities.target_class, category=entities.category, exam=entities.exam)

        if tool == "get_fee":
            from app.tools.structured import FeeToolInput
            return FeeToolInput(course_name=entities.course, course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None)

        if tool == "get_branch_info":
            from app.tools.structured import BranchInfoToolInput
            return BranchInfoToolInput(branch_name=entities.branch, branch_id=entities.additional_entities.get("branch_id") if entities and entities.additional_entities else None)

        if tool == "get_eligibility":
            from app.tools.structured import EligibilityToolInput
            return EligibilityToolInput(program_name=entities.program or entities.course, course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None, target_class=entities.target_class)

        if tool == "get_admission_steps":
            from app.tools.structured import AdmissionStepsToolInput
            return AdmissionStepsToolInput()

        if tool == "get_admission_status":
            from app.tools.structured import AdmissionStatusToolInput
            return AdmissionStatusToolInput()

        if tool == "get_availability":
            from app.tools.structured import AvailabilityToolInput
            return AvailabilityToolInput()

        return None


# Factory helper to allow tests to inject a fake engine
_global_engine: Optional[ExecutionEngine] = None


def get_execution_engine(structured_service: Any = None, retriever: Any = None) -> ExecutionEngine:
    global _global_engine
    if _global_engine:
        return _global_engine
    return ExecutionEngine(structured_service=structured_service, retriever=retriever)


def set_global_execution_engine(engine: ExecutionEngine) -> None:
    global _global_engine
    _global_engine = engine


__all__ = ["ExecutionEngine", "get_execution_engine", "set_global_execution_engine"]
