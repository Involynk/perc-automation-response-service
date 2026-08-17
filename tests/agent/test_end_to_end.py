import json
from pathlib import Path
from typing import List

from app.agent.graph import build_response_graph
from app.agent.executor import ExecutionEngine, set_global_execution_engine
from app.agent.generator import DraftAnswerModel
from app.schemas.agent import AgentState, ToolResult, RetrievedDocument, QueryIntent
from app.agent.router import decide_routing


MOCK_ROOT = Path("MockData")


class FakeStructuredService:
    def __init__(self, root: Path = MOCK_ROOT / "structured"):
        self.root = Path(root)
        self._courses = json.loads((self.root / "courses.json").read_text(encoding="utf-8-sig"))
        self._fees = json.loads((self.root / "fees.json").read_text(encoding="utf-8-sig"))
        self._elig = json.loads((self.root / "eligibility.json").read_text(encoding="utf-8-sig"))
        self._branches = json.loads((self.root / "branches.json").read_text(encoding="utf-8-sig"))
        self._availability = json.loads((self.root / "availability.json").read_text(encoding="utf-8-sig"))
        self._admission = json.loads((self.root / "admission-status.json").read_text(encoding="utf-8-sig"))

    # Minimal methods used by structured tools
    def get_course_by_name(self, name: str):
        if not name:
            return None
        for c in self._courses:
            if c.get("name", "").lower() == name.lower():
                from app.schemas.structured import CourseResponseSchema

                return CourseResponseSchema.model_validate(c) if hasattr(CourseResponseSchema, "model_validate") else CourseResponseSchema(**c)
        return None

    def get_course_by_id(self, course_id: str):
        if not course_id:
            return None
        for c in self._courses:
            if c.get("id") == course_id:
                from app.schemas.structured import CourseResponseSchema

                return CourseResponseSchema.model_validate(c) if hasattr(CourseResponseSchema, "model_validate") else CourseResponseSchema(**c)
        return None

    def get_program_fee(self, course_id: str):
        for p in self._fees.get("programs", []):
            if p.get("id") == course_id or p.get("name", "").lower() == course_id.lower():
                from app.schemas.structured import ProgramFeeResponseSchema

                return ProgramFeeResponseSchema.model_validate(p) if hasattr(ProgramFeeResponseSchema, "model_validate") else ProgramFeeResponseSchema(**p)
        return None

    def list_program_fees(self):
        from app.schemas.structured import ProgramFeeResponseSchema

        return [ProgramFeeResponseSchema.model_validate(p) if hasattr(ProgramFeeResponseSchema, "model_validate") else ProgramFeeResponseSchema(**p) for p in self._fees.get("programs", [])]

    def get_fee_policy(self):
        from app.schemas.structured import FeePolicyResponseSchema

        policy = {k: v for k, v in self._fees.items() if k != "programs"}
        return FeePolicyResponseSchema.model_validate(policy) if hasattr(FeePolicyResponseSchema, "model_validate") else FeePolicyResponseSchema(**policy)

    def get_program_eligibility(self, program_name: str):
        for p in self._elig.get("program_eligibility", []):
            if p.get("program", "").lower() == (program_name or "").lower():
                from app.schemas.structured import ProgramEligibilityResponseSchema

                data = {
                    "program_name": p.get("program"),
                    "course_id": None,
                    "min_class": p.get("min_class"),
                    "max_class": p.get("max_class"),
                    "notes": p.get("notes"),
                }
                return ProgramEligibilityResponseSchema.model_validate(data) if hasattr(ProgramEligibilityResponseSchema, "model_validate") else ProgramEligibilityResponseSchema(**data)
        return None

    def get_availability_info(self):
        from app.schemas.structured import AvailabilityInfoResponseSchema

        return AvailabilityInfoResponseSchema.model_validate(self._availability) if hasattr(AvailabilityInfoResponseSchema, "model_validate") else AvailabilityInfoResponseSchema(**self._availability)

    def get_admission_status(self):
        from app.schemas.structured import AdmissionStatusResponseSchema

        return AdmissionStatusResponseSchema.model_validate(self._admission) if hasattr(AdmissionStatusResponseSchema, "model_validate") else AdmissionStatusResponseSchema(**self._admission)


class FakeRetriever:
    def __init__(self, root: Path = MOCK_ROOT / "unstructured"):
        self.root = Path(root)
        self.docs = {}
        for p in self.root.glob("*.md"):
            self.docs[p.name] = p.read_text(encoding="utf-8-sig")

    def search(self, query: str, top_k: int = 3) -> List[RetrievedDocument]:
        # Simple substring match ranking
        q = (query or "").lower()
        scored = []
        for name, content in self.docs.items():
            score = sum(1 for w in q.split() if w and w in content.lower())
            if score > 0:
                scored.append((score, name, content))
        scored.sort(reverse=True)
        out = []
        for score, name, content in scored[:top_k]:
            out.append(RetrievedDocument(source_file=str(Path("MockData") / "unstructured" / name), content=content[:1000], relevance_score=min(1.0, score / 5.0), metadata={}))
        # Fallback: return the first doc if nothing matched
        if not out:
            name, content = next(iter(self.docs.items()))
            out.append(RetrievedDocument(source_file=str(Path("MockData") / "unstructured" / name), content=content[:1000], relevance_score=0.5, metadata={}))
        return out


def _fake_generate(self, state: AgentState) -> DraftAnswerModel:
    # Create deterministic draft from state evidence
    used_structured = any(getattr(tr, "metadata", {}).get("source") == "structured_database" for tr in getattr(state, "tool_results", []) or [])
    used_rag = len(getattr(state, "retrieved_documents", []) or []) > 0
    evidence = []
    for tr in getattr(state, "tool_results", []) or []:
        if tr.success:
            evidence.append({"tool_name": tr.tool_name, "data": tr.data})
    for rd in getattr(state, "retrieved_documents", []) or []:
        evidence.append({"source_file": rd.source_file, "snippet": (rd.content[:80] if rd.content else "")})

    draft_obj = {
        "draft_answer": f"DRAFT for query: {state.query}",
        "used_structured": used_structured,
        "used_rag": used_rag,
        "evidence": evidence,
        "confidence": 0.9,
    }
    # Return a DraftAnswerModel whose `draft_answer` is a JSON string of the payload
    return DraftAnswerModel(draft_answer=json.dumps(draft_obj), used_structured=used_structured, used_rag=used_rag, evidence=evidence, confidence=0.9)


def test_end_to_end_integration(monkeypatch):
    # Build fake services and inject engine
    fake_struct = FakeStructuredService()
    fake_retriever = FakeRetriever()
    engine = ExecutionEngine(structured_service=fake_struct, retriever=fake_retriever)
    set_global_execution_engine(engine)

    # Patch generator to avoid any LLM calls; stub __init__ to avoid real client construction
    monkeypatch.setattr("app.agent.generator.AnswerGenerator.__init__", lambda self, client=None: setattr(self, 'client', None) or None, raising=True)
    monkeypatch.setattr("app.agent.generator.AnswerGenerator.generate", _fake_generate, raising=True)

    # Load test cases and pick the first 15 representative cases
    cases = json.loads(Path("tests/agent/query_understanding_cases.json").read_text(encoding="utf-8-sig"))
    selected = cases[:15]

    # Sanity check: provider must work deterministically on mock data
    from app.agent.providers.factory import get_query_understanding_provider
    prov = get_query_understanding_provider()

    graph = build_response_graph()

    failures = []
    for c in selected:
        # include conversation context when present so understand_node can detect follow-ups
        req = {"session_id": c["id"], "query": c["query"]}
        if c.get("context"):
            req["metadata"] = {"conversation_context": c.get("context")}
        out = graph.invoke(req)
        mapping = out if isinstance(out, dict) else (out.model_dump() if hasattr(out, "model_dump") else out)
        validated = AgentState.model_validate(mapping) if hasattr(AgentState, "model_validate") else AgentState(**mapping)

        # 1) Understanding must produce expected primary intent
        # Quick provider-level assert to help debug failures
        prov_result = prov.analyze(c["query"], context=c.get("context") or [])
        assert isinstance(prov_result, dict) and "primary_intent" in prov_result
        assert validated.intent is not None
        assert validated.intent.value == c["expected_primary_intent"]

        # 2) Routing must match router's decision
        rd = validated.metadata.get("routing_decision")
        expected_rd = decide_routing(validated.intent, validated.secondary_intents, validated.ambiguity, validated.entities.model_dump() if hasattr(validated.entities, "model_dump") else {}, validated.query)
        # compare route type
        assert rd is not None
        assert rd["route"] == expected_rd.route.value

        # 3) Execution: structured vs rag
        if expected_rd.route.value == "STRUCTURED_TOOL":
            # expect a tool_result for the chosen tool
            tool_names = [tr.tool_name for tr in validated.tool_results]
            assert expected_rd.tool_name in tool_names
        elif expected_rd.route.value == "RAG":
            # expect rag_search tool result and retrieved_documents
            tool_names = [tr.tool_name for tr in validated.tool_results]
            assert "rag_search" in tool_names
            assert len(validated.retrieved_documents) > 0
        elif expected_rd.route.value == "MULTI_INTENT":
            # expect multiple structured tool_results or rag entries depending on subs
            assert len(validated.tool_results) > 0 or len(validated.retrieved_documents) > 0

        # 4) Result check present
        assert validated.result_check is not None

        # 5) Generation + Validation behavior
        rc = validated.result_check
        # result_check may be a dict (from compiled graph) or a model
        rc_is_sufficient = rc.get("is_sufficient") if isinstance(rc, dict) else getattr(rc, "is_sufficient", False)
        rc_requires_clarification = rc.get("requires_clarification") if isinstance(rc, dict) else getattr(rc, "requires_clarification", False)
        rc_requires_human = rc.get("requires_human_handoff") if isinstance(rc, dict) else getattr(rc, "requires_human_handoff", False)

        if rc_is_sufficient and not rc_requires_clarification and not rc_requires_human:
            # generation should have produced a draft and validation should mark status validated
            assert validated.draft_answer is not None
            assert validated.metadata.get("generation_status") == "ok"
            assert validated.metadata.get("validation_status") == "validated"
        else:
            # generation should have been skipped or no valid draft
            assert validated.draft_answer is None or validated.metadata.get("generation_status") == "skipped_insufficient_evidence"

    assert len(failures) == 0
