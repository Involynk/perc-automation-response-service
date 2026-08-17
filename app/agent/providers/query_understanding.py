from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.agent import (
    QueryIntent,
    ExtractedEntities,
    AmbiguityCheck,
)


class QueryUnderstandingProvider:
    """Interface for query understanding providers."""

    def analyze(self, query: str, context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        raise NotImplementedError()


class MockDataProvider(QueryUnderstandingProvider):
    """Production provider that uses the repository's MockData as the authoritative
    source of truth to determine intents, extract entities, and detect ambiguity.

    This is deliberately deterministic and rule-based so it can run offline in
    tests and produce reproducible outputs.
    """

    def __init__(self, repo_root: Optional[Path] = None):
        self.root = Path(repo_root or Path(__file__).resolve().parents[3])
        # load course names for entity matching
        try:
            data_path = self.root / "MockData" / "structured" / "courses.json"
            # handle possible UTF-8 BOM in files
            self.courses = json.loads(data_path.read_text(encoding="utf-8-sig"))
            self.course_names = [c["name"].lower() for c in self.courses]
            # map lowercase name -> original name for entity output
            self._course_name_map = {c["name"].lower(): c["name"] for c in self.courses}
        except Exception:
            self.courses = []
            self.course_names = []

    def _find_program(self, text: str) -> Optional[str]:
        t = text.lower()
        for name in self.course_names:
            if name in t:
                return self._course_name_map.get(name)
        # also try short forms like 'jEE' or 'NEET'
        for c in self.courses:
            if c.get("category", "").lower() in t or c.get("id", "").lower() in t:
                return c["name"]
        return None

    def analyze(self, query: str, context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        q = (query or "").strip()
        ctx = context or []

        if not q:
            return {
                "primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value,
                "secondary_intents": [],
                "entities": {},
                "ambiguity": {"is_ambiguous": True, "missing_information": ["query"]},
                "confidence": 0.0,
            }

        # simple keyword rules
        lower = q.lower()

        # out-of-scope detection
        if "byju" in lower or "byju" in lower or "which is better" in lower:
            pri = QueryIntent.OUT_OF_SCOPE_ESCALATION
            return {"primary_intent": pri.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        # grievance
        if any(w in lower for w in ("complaint", "grievance", "file a complaint")):
            return {"primary_intent": QueryIntent.GRIEVANCE_HUMAN_HANDOFF.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        # hostel
        if "hostel" in lower or "accommodation" in lower:
            return {"primary_intent": QueryIntent.HOSTEL_ACCOMMODATION.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        # placement
        if "placement" in lower or "placement records" in lower:
            return {"primary_intent": QueryIntent.PLACEMENT_CAREER_OUTCOMES.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        # language medium
        if "medium" in lower or "language" in lower:
            return {"primary_intent": QueryIntent.LANGUAGE_MEDIUM.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        # fees
        is_fee = any(w in lower for w in ("fee", "fees", "price", "cost"))
        is_docs = any(w in lower for w in ("document", "documents", "required documents"))
        is_adm = any(w in lower for w in ("admission", "enroll", "how do i take admission", "join"))
        is_where = any(w in lower for w in ("where", "located", "address"))
        is_avail = any(w in lower for w in ("admissions: open", "admissions open", "open now", "available"))
        is_compare = any(w in lower for w in ("different", "compare", "how is", "better than"))
        is_policy = any(w in lower for w in ("policy", "batch size", "refund", "privacy"))

        # try extracting program from query or context
        program = self._find_program(q) or (self._find_program(ctx[-1]["text"]) if ctx else None)

        secondary: List[str] = []
        # if a known program is mentioned with an intent-like verb, prefer course details
        if program and any(w in lower for w in ("tell", "about", "details", "describe")):
            return {"primary_intent": QueryIntent.COURSE_DETAILS.value, "secondary_intents": [], "entities": {"program": program}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        # multi-intent detection
        if is_fee and is_docs:
            # multi-intent example
            return {
                "primary_intent": QueryIntent.MULTI_INTENT.value,
                "secondary_intents": [QueryIntent.FEES_PRICING.value, QueryIntent.REQUIRED_DOCUMENTS.value],
                "entities": {"program": program} if program else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.9,
            }

        # follow-up contextual: if there is conversation context and query is short
        if ctx and len(q.split()) <= 6:
            return {
                "primary_intent": QueryIntent.FOLLOW_UP_CONTEXTUAL.value,
                "secondary_intents": [],
                "entities": {"program": program} if program else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.9,
            }

        if is_fee:
            # If fee query lacks program, treat as ambiguous/incomplete per dataset rules
            if not program:
                return {"primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": True, "missing_information": ["program"]}, "confidence": 0.2}
            ambiguity = {"is_ambiguous": False}
            return {"primary_intent": QueryIntent.FEES_PRICING.value, "secondary_intents": [], "entities": {"program": program}, "ambiguity": ambiguity, "confidence": 0.9}

        if is_docs:
            # documents can be asked generally without a program
            ambiguity = {"is_ambiguous": False}
            return {"primary_intent": QueryIntent.REQUIRED_DOCUMENTS.value, "secondary_intents": [], "entities": {"program": program} if program else {}, "ambiguity": ambiguity, "confidence": 0.9}

        # availability check: questions like "Are admissions open?"
        if ("open" in lower or "available" in lower) and "admission" in lower:
            return {"primary_intent": QueryIntent.AVAILABILITY_STATUS.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        # distinguish eligibility queries like "Who can join X" from general admission process
        if ("who can join" in lower or ("who can" in lower and program)):
            return {"primary_intent": QueryIntent.ELIGIBILITY.value, "secondary_intents": [], "entities": {"program": program} if program else {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.95}

        if is_adm:
            return {"primary_intent": QueryIntent.ADMISSION_PROCESS.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        if is_where:
            return {"primary_intent": QueryIntent.BRANCH_LOCATION.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        if is_avail:
            return {"primary_intent": QueryIntent.AVAILABILITY_STATUS.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        if is_compare:
            return {"primary_intent": QueryIntent.COMPARISON.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.85}

        if is_policy:
            return {"primary_intent": QueryIntent.POLICIES.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.85}

        # course discovery fallback
        if any(w in lower for w in ("course", "courses", "programs", "offer")):
            return {"primary_intent": QueryIntent.COURSE_DISCOVERY.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": False}, "confidence": 0.9}

        # otherwise default to ambiguous/incomplete
        return {"primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value, "secondary_intents": [], "entities": {}, "ambiguity": {"is_ambiguous": True, "missing_information": ["intent"]}, "confidence": 0.2}


__all__ = ["QueryUnderstandingProvider", "MockDataProvider"]
