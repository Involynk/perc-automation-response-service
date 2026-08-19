import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.agent import AgentState, ToolResult, RetrievedDocument
from app.agent.router import RouteType, RoutingDecision

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Centralized execution engine for Phase 5D.

    Constructs real DB-backed services (StructuredDataService, KnowledgeRetriever)
    on demand if not explicitly injected by tests.
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
                    state.tool_results.append(ToolResult(tool_name=tool, success=False, error="Missing parameters for tool execution", metadata={"reason": "missing_parameters"}))
                    return

                service = self.structured_service
                db_session = None
                if service is None:
                    from app.db.session import SessionLocal
                    from app.services.structured_data_service import StructuredDataService
                    db_session = SessionLocal()
                    service = StructuredDataService(db_session)

                try:
                    func = self._tool_map[tool]
                    result = func(service, params)
                    state.tool_results.append(result)
                except Exception as exc:
                    logger.error(f"Error executing structured tool {tool}: {exc}", exc_info=True)
                    state.tool_results.append(ToolResult(tool_name=tool, success=False, error=str(exc), metadata={}))
                finally:
                    if db_session is not None:
                        db_session.close()

            elif route.route == RouteType.RAG:
                retriever = self.retriever
                db_session = None
                if retriever is None:
                    from app.db.session import SessionLocal
                    from app.rag.retrieval import KnowledgeRetriever
                    db_session = SessionLocal()
                    retriever = KnowledgeRetriever(db_session)

                try:
                    top_k = 3
                    docs = retriever.search(state.query or "", top_k=top_k)
                    rd_list = [RetrievedDocument.model_validate(d.model_dump()) if hasattr(d, "model_dump") else d for d in docs]
                    state.retrieved_documents.extend(rd_list)
                    state.tool_results.append(ToolResult(tool_name="rag_search", success=True, data=[d.model_dump() for d in rd_list], metadata={"count": len(rd_list)}))
                except Exception as exc:
                    logger.error(f"Error executing RAG search for query \"{state.query}\": {exc}", exc_info=True)
                    state.tool_results.append(ToolResult(tool_name="rag_search", success=False, error=str(exc), metadata={}))
                finally:
                    if db_session is not None:
                        db_session.close()

            elif route.route == RouteType.CLARIFICATION:
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

        if "execution_status" not in state.metadata:
            state.metadata["execution_status"] = "ok"

        return state

    def _build_tool_params(self, tool: str, state: AgentState) -> Optional[Any]:
        entities = state.entities
        q = state.query

        if tool == "get_course_info":
            from app.tools.structured import CourseInfoToolInput
            return CourseInfoToolInput(
                course_name=entities.course or entities.program if entities else None,
                course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None,
                target_class=entities.target_class if entities else None,
                category=entities.category if entities else None,
                exam=entities.exam if entities else None,
            )

        if tool == "get_fee":
            from app.tools.structured import FeeToolInput
            return FeeToolInput(
                course_name=entities.course or entities.program if entities else None,
                course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None,
            )

        if tool == "get_branch_info":
            from app.tools.structured import BranchInfoToolInput
            return BranchInfoToolInput(
                branch_name=entities.branch if entities else None,
                branch_id=entities.additional_entities.get("branch_id") if entities and entities.additional_entities else None,
            )

        if tool == "get_eligibility":
            from app.tools.structured import EligibilityToolInput
            return EligibilityToolInput(
                program_name=entities.program or entities.course if entities else None,
                course_id=entities.additional_entities.get("course_id") if entities and entities.additional_entities else None,
                target_class=entities.target_class if entities else None,
            )

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
