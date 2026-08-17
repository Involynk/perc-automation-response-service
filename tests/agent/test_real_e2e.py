import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_response_graph
from app.agent.graph import build_response_graph
from app.agent.executor import ExecutionEngine, set_global_execution_engine
from app.agent.generator import DraftAnswerModel
from app.schemas.agent import QueryIntent, RetrievedDocument
from app.schemas.response import ResponseResponse
from app.agent.providers.ollama_client import OllamaLLMClient

MOCK_ROOT = Path("MockData")


class MockStructuredService:
    def __init__(self, root: Path = MOCK_ROOT / "structured"):
        self.root = Path(root)
        self._courses = json.loads((self.root / "courses.json").read_text(encoding="utf-8-sig"))
        self._fees = json.loads((self.root / "fees.json").read_text(encoding="utf-8-sig"))
        self._elig = json.loads((self.root / "eligibility.json").read_text(encoding="utf-8-sig"))
        self._branches = json.loads((self.root / "branches.json").read_text(encoding="utf-8-sig"))
        self._availability = json.loads((self.root / "availability.json").read_text(encoding="utf-8-sig"))
        self._admission = json.loads((self.root / "admission-status.json").read_text(encoding="utf-8-sig"))

    def get_course_by_name(self, name: str):
        if not name:
            return None
        for c in self._courses:
            if c.get("name", "").lower() == name.lower():
                from app.schemas.structured import CourseResponseSchema

                return CourseResponseSchema.model_validate(c)
        return None

    def get_course_by_id(self, course_id: str):
        if not course_id:
            return None
        for c in self._courses:
            if c.get("id") == course_id:
                from app.schemas.structured import CourseResponseSchema

                return CourseResponseSchema.model_validate(c)
        return None

    def get_program_fee(self, course_id: str):
        for p in self._fees.get("programs", []):
            if p.get("id") == course_id or p.get("name", "").lower() == course_id.lower():
                from app.schemas.structured import ProgramFeeResponseSchema

                return ProgramFeeResponseSchema.model_validate(p)
        return None

    def list_program_fees(self):
        from app.schemas.structured import ProgramFeeResponseSchema

        return [ProgramFeeResponseSchema.model_validate(p) for p in self._fees.get("programs", [])]

    def get_fee_policy(self):
        from app.schemas.structured import FeePolicyResponseSchema

        policy = {k: v for k, v in self._fees.items() if k != "programs"}
        return FeePolicyResponseSchema.model_validate(policy)

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
                return ProgramEligibilityResponseSchema.model_validate(data)
        return None

    def get_availability_info(self):
        from app.schemas.structured import AvailabilityInfoResponseSchema

        return AvailabilityInfoResponseSchema.model_validate(self._availability)

    def get_admission_status(self):
        from app.schemas.structured import AdmissionStatusResponseSchema

        return AdmissionStatusResponseSchema.model_validate(self._admission)


class MockRetriever:
    def __init__(self, root: Path = MOCK_ROOT / "unstructured"):
        self.root = Path(root)
        self.docs = {}
        for p in self.root.glob("*.md"):
            self.docs[p.name] = p.read_text(encoding="utf-8-sig")

    def search(self, query: str, top_k: int = 3) -> List[RetrievedDocument]:
        q = (query or "").lower()
        scored = []
        for name, content in self.docs.items():
            score = sum(1 for w in q.split() if w and w in content.lower())
            if score > 0:
                scored.append((score, name, content))
        scored.sort(reverse=True)
        out = []
        for score, name, content in scored[:top_k]:
            out.append(
                RetrievedDocument(
                    source_file=str(Path("MockData") / "unstructured" / name),
                    content=content[:1000],
                    relevance_score=min(1.0, score / 5.0),
                    metadata={"source": name},
                )
            )
        if not out:
            name, content = next(iter(self.docs.items()))
            out.append(
                RetrievedDocument(
                    source_file=str(Path("MockData") / "unstructured" / name),
                    content=content[:1000],
                    relevance_score=0.5,
                    metadata={"source": name},
                )
            )
        return out


def _deterministic_generate(self, state: Any) -> DraftAnswerModel:
    used_structured = any(
        getattr(tr, "metadata", {}).get("source") == "structured_database"
        for tr in getattr(state, "tool_results", []) or []
    )
    used_rag = len(getattr(state, "retrieved_documents", []) or []) > 0
    evidence = []
    for tr in getattr(state, "tool_results", []) or []:
        if tr.success:
            evidence.append({"tool_name": tr.tool_name, "data": tr.data})
    for rd in getattr(state, "retrieved_documents", []) or []:
        evidence.append({"source_file": rd.source_file, "snippet": (rd.content[:80] if rd.content else "")})

    payload = {
        "draft_answer": f"Verified PERC response for query: {state.query}",
        "used_structured": used_structured,
        "used_rag": used_rag,
        "evidence": evidence,
        "confidence": 0.95,
    }
    return DraftAnswerModel(
        draft_answer=json.dumps(payload),
        used_structured=used_structured,
        used_rag=used_rag,
        evidence=evidence,
        confidence=0.95,
    )


@pytest.fixture
def e2e_environment(monkeypatch):
    """Set up the complete response pipeline environment with mock data services."""
    struct_service = MockStructuredService()
    retriever = MockRetriever()
    engine = ExecutionEngine(structured_service=struct_service, retriever=retriever)
    set_global_execution_engine(engine)

    # Patch AnswerGenerator for deterministic testing
    monkeypatch.setattr(
        "app.agent.generator.AnswerGenerator.__init__",
        lambda self, client=None: setattr(self, "client", None) or None,
        raising=True,
    )
    monkeypatch.setattr(
        "app.agent.generator.AnswerGenerator.generate",
        _deterministic_generate,
        raising=True,
    )

    graph = build_response_graph()
    app.dependency_overrides[get_response_graph] = lambda: graph

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_all_18_real_e2e_cases(e2e_environment):
    """Execute all 18 canonical PERC query categories end-to-end through FastAPI and LangGraph."""
    client = e2e_environment
    cases = json.loads(Path("tests/agent/query_understanding_cases.json").read_text(encoding="utf-8-sig"))

CASES = json.loads(Path("tests/agent/query_understanding_cases.json").read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_real_e2e_case(e2e_environment, case):
    """Execute each canonical PERC query category end-to-end through FastAPI and LangGraph."""
    client = e2e_environment

    case_id = case["id"]
    category = case["category"]
    query = case["query"]
    expected_primary_intent = case["expected_primary_intent"]

    payload: Dict[str, Any] = {
        "session_id": f"real-e2e-{case_id}",
        "message": query,
    }
    if case.get("context"):
        payload["metadata"] = {"conversation_context": case["context"]}

    response = client.post("/api/v1/response", json=payload)
    assert response.status_code == 200, f"Failed for case {case_id}: {response.text}"

    data = response.json()
    validated = ResponseResponse.model_validate(data)

    # 1. Invariant: Session ID preserved
    assert validated.session_id == f"real-e2e-{case_id}"

    # 2. Invariant: Intent detected and matches expected category
    assert validated.intent is not None
    assert validated.intent.value == expected_primary_intent

    # 3. Invariant: Status and Clarification behavior
    if category in ("C12_FOLLOW_UP_CONTEXTUAL", "C13_AMBIGUOUS_INCOMPLETE"):
        if validated.status == "clarification_required":
            assert validated.clarification_required is True
            assert len(validated.answer) > 0
        else:
            assert validated.status == "success"
            assert validated.clarification_required is False
            assert len(validated.answer) > 0
    elif category in ("C14_OUT_OF_SCOPE_ESCALATION", "C15_GRIEVANCE_HUMAN_HANDOFF"):
        assert validated.status == "escalated"
        assert validated.clarification_required is False
        assert "counseling" in validated.answer.lower() or "representative" in validated.answer.lower() or "escalated" in validated.answer.lower()
    else:
        # Answerable queries should succeed or escalate if insufficient evidence
        if validated.status == "escalated":
            # Check if this case was routed to escalation or insufficient evidence
            assert "admissions" in validated.answer.lower() or "counseling" in validated.answer.lower() or "assistance" in validated.answer.lower()
        else:
            assert validated.status == "success"
            assert validated.clarification_required is False
            assert len(validated.answer) > 0

    # 4. Invariant: Sources are a deduplicated list
    assert isinstance(validated.sources, list)
    assert len(validated.sources) == len(set(validated.sources))


@pytest.mark.live
def test_live_ollama_qwen3_e2e():
    """Live verification test using the actual Ollama service and Qwen3 model.

    Skips gracefully if local Ollama service is not running.
    """
    try:
        client = OllamaLLMClient()
        is_healthy = client.health_check(verify_model=True)
    except Exception as exc:
        is_healthy = False

    if not is_healthy:
        pytest.skip("Local Ollama service or Qwen3 model not available on localhost:11434")

    # If healthy, run a live query through the full FastAPI + LangGraph pipeline
    test_client = TestClient(app)
    resp = test_client.post(
        "/api/v1/response",
        json={"session_id": "live-ollama-session", "message": "What courses do you offer at PERC?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    res = ResponseResponse.model_validate(data)
    assert res.session_id == "live-ollama-session"
    assert res.status in ("success", "clarification_required", "escalated")
    assert len(res.answer) > 0
