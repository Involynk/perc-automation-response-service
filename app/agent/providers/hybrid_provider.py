from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.agent import QueryIntent
from app.core.config import settings
from .query_understanding import QueryUnderstandingProvider, MockDataProvider
from .llm_query_provider import LLMQueryProvider, BaseLLMClient
from .ollama_client import OllamaLLMClient, OllamaError
from .groq_client import GroqClient, GroqError

logger = logging.getLogger(__name__)


class DeterministicFastPathClassifier:
    """
    Ultra-fast (< 1ms) rule-based and entity-matching classifier for deterministic queries.
    Prevents expensive LLM / Ollama calls for routine educational queries.
    """

    KNOWN_COURSES = [
        "PERC Ignite",
        "PERC Explorer",
        "PERC Challenger",
        "PERC Achiever",
        "PERC Champion",
        "NEET Foundation",
        "NEET UG",
        "JEE Foundation",
        "IIT-JEE Advanced",
        "KCET Crash Course",
        "CBSE Board Coaching",
        "ICSE Board Coaching",
        "Olympiad Foundation",
        "One-to-One Tuition",
    ]

    KNOWN_BRANCHES = ["Ujire", "Begur", "Main Campus", "Bangalore", "Dharmasthala"]

    def __init__(self):
        self._course_map = {c.lower(): c for c in self.KNOWN_COURSES}
        self._aliases = {
            "ignite": "PERC Ignite",
            "explorer": "PERC Explorer",
            "challenger": "PERC Challenger",
            "achiever": "PERC Achiever",
            "champion": "PERC Champion",
            "neet ug": "NEET UG",
            "neet": "NEET UG",
            "jee foundation": "JEE Foundation",
            "jee advanced": "IIT-JEE Advanced",
            "iit jee": "IIT-JEE Advanced",
            "jee": "JEE Foundation",
            "kcet": "KCET Crash Course",
            "cbse": "CBSE Board Coaching",
            "icse": "ICSE Board Coaching",
            "olympiad": "Olympiad Foundation",
            "tuition": "One-to-One Tuition",
            "one to one": "One-to-One Tuition",
        }

    def find_course(self, text: str) -> Optional[str]:
        t = text.lower()
        for k, v in self._course_map.items():
            if k in t:
                return v
        for k, v in self._aliases.items():
            pattern = rf"\b{re.escape(k)}\b"
            if re.search(pattern, t):
                return v
        return None

    def find_branch(self, text: str) -> Optional[str]:
        t = text.lower()
        for b in self.KNOWN_BRANCHES:
            if b.lower() in t:
                return b
        return None

    def classify(self, query: str, context: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Attempt fast deterministic classification.
        Returns a complete result dict if confident, or None if LLM is required.
        """
        q = (query or "").strip()
        lower = q.lower()

        if not q:
            return {
                "primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value,
                "secondary_intents": [],
                "entities": {},
                "ambiguity": {"is_ambiguous": True, "missing_information": ["query"]},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 1. Greetings / Conversational openers
        greeting_patterns = [
            r"^(hi|hello|hey|good morning|good afternoon|good evening|namaste|greetings)[\s!.]*$",
            r"^(help|can you help me|need help|i have a question)[\s!.]*$",
        ]
        for gp in greeting_patterns:
            if re.match(gp, lower):
                return {
                    "primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value,
                    "secondary_intents": [],
                    "entities": {},
                    "ambiguity": {
                        "is_ambiguous": True,
                        "clarification_required": True,
                        "clarification_question": "Hello! How can I assist you with PERC courses, admissions, or fees today?",
                        "missing_information": ["specific_topic"],
                    },
                    "confidence": 0.95,
                    "classified_by": "deterministic_fast_path",
                }

        # 2. Out-of-scope & Grievance
        if any(w in lower for w in ("byju", "allen", "unacademy", "physics wallah", "which institute is better")):
            return {
                "primary_intent": QueryIntent.OUT_OF_SCOPE_ESCALATION.value,
                "secondary_intents": [],
                "entities": {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        if any(w in lower for w in ("complaint", "grievance", "refund issue", "file a complaint", "bad service")):
            return {
                "primary_intent": QueryIntent.GRIEVANCE_HUMAN_HANDOFF.value,
                "secondary_intents": [],
                "entities": {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 3. Course Discovery (All courses / programs list / "What does PERC offer?")
        discovery_patterns = [
            r"\b(what|which|list|show|give|tell me)\b.*\b(courses|programs|classes|batches|offer|provide)\b",
            r"\b(what courses|available courses|offer courses|what programs|available programs|what does perc offer)\b",
            r"\b(what do you offer|what are you offering|courses available|programs available)\b",
            r"^(courses|programs|all courses|all programs|course list)[\s?!.]*$",
        ]
        for dp in discovery_patterns:
            if re.search(dp, lower):
                course = self.find_course(q)
                if not course or "all" in lower or "what courses" in lower or "available" in lower or "what does perc offer" in lower:
                    return {
                        "primary_intent": QueryIntent.COURSE_DISCOVERY.value,
                        "secondary_intents": [],
                        "entities": {},
                        "ambiguity": {"is_ambiguous": False},
                        "confidence": 0.95,
                        "classified_by": "deterministic_fast_path",
                    }

        course = self.find_course(q)
        branch = self.find_branch(q)

        # 4. Fee & Pricing
        fee_keywords = ("fee", "fees", "pricing", "cost", "how much", "price", "charge", "charges", "tuition fee")
        is_fee = any(kw in lower for kw in fee_keywords)

        if is_fee:
            if not course:
                return {
                    "primary_intent": QueryIntent.AMBIGUOUS_INCOMPLETE.value,
                    "secondary_intents": [QueryIntent.FEES_PRICING.value],
                    "entities": {"branch": branch} if branch else {},
                    "ambiguity": {
                        "is_ambiguous": True,
                        "clarification_required": True,
                        "clarification_question": "Could you please specify which course or program you are inquiring about?",
                        "missing_information": ["program"],
                    },
                    "confidence": 0.95,
                    "classified_by": "deterministic_fast_path",
                }
            entities = {"program": course, "course": course}
            if branch:
                entities["branch"] = branch
            return {
                "primary_intent": QueryIntent.FEES_PRICING.value,
                "secondary_intents": [],
                "entities": entities,
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 5. Eligibility Rules
        eligibility_keywords = ("eligibility", "eligible", "who can join", "who can apply", "criteria", "qualification", "percentage required")
        if any(kw in lower for kw in eligibility_keywords):
            return {
                "primary_intent": QueryIntent.ELIGIBILITY.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course} if course else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 6. Course Details & Attributes (Duration, Subjects, Overview)
        detail_keywords = (
            "tell me about", "details of", "about", "what is", "explain", "info on",
            "syllabus", "duration", "how long", "subjects", "what subjects", "which subjects"
        )
        if course and (any(kw in lower for kw in detail_keywords) or len(q.split()) <= 4):
            return {
                "primary_intent": QueryIntent.COURSE_DETAILS.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 7. Branch / Location / Campus
        location_keywords = ("where", "location", "address", "branches", "campus", "center", "centre", "reach")
        if any(kw in lower for kw in location_keywords):
            entities = {}
            if branch:
                entities["branch"] = branch
            return {
                "primary_intent": QueryIntent.BRANCH_LOCATION.value,
                "secondary_intents": [],
                "entities": entities,
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 8. Required Documents
        doc_keywords = ("document", "documents", "certificate", "marks card", "id proof", "what to bring")
        if any(kw in lower for kw in doc_keywords):
            return {
                "primary_intent": QueryIntent.REQUIRED_DOCUMENTS.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course} if course else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 9. Admission Process & Steps
        admission_keywords = ("how to apply", "how do i join", "admission process", "steps for admission", "how to enroll", "enrollment")
        if any(kw in lower for kw in admission_keywords):
            return {
                "primary_intent": QueryIntent.ADMISSION_PROCESS.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course} if course else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 10. Availability Status (Admissions open?)
        if ("open" in lower or "available" in lower) and any(w in lower for w in ("admission", "seat", "batch", "enrollment")):
            return {
                "primary_intent": QueryIntent.AVAILABILITY_STATUS.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course} if course else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 11. Scholarships
        if "scholarship" in lower or "discount" in lower or "concession" in lower:
            return {
                "primary_intent": QueryIntent.POLICIES.value,
                "secondary_intents": [],
                "entities": {"program": course, "course": course} if course else {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        # 12. Hostel & Accommodation
        if "hostel" in lower or "stay" in lower or "accommodation" in lower:
            return {
                "primary_intent": QueryIntent.HOSTEL_ACCOMMODATION.value,
                "secondary_intents": [],
                "entities": {},
                "ambiguity": {"is_ambiguous": False},
                "confidence": 0.95,
                "classified_by": "deterministic_fast_path",
            }

        return None


class HybridQueryUnderstandingProvider(QueryUnderstandingProvider):
    """
    Production Hybrid Query Understanding Provider:
    1. Runs DeterministicFastPathClassifier first (0ms, 100% deterministic, 0 LLM tokens).
    2. Only delegates to Ollama LLM provider for complex or unclassified queries.
    3. Handles LLM timeout/failure gracefully with deterministic fallback.
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.fast_path = DeterministicFastPathClassifier()
        self.mock_provider = MockDataProvider()
        self.llm_client = llm_client

    def _get_llm_provider(self) -> Optional[LLMQueryProvider]:
        if self.llm_client is not None:
            return LLMQueryProvider(client=self.llm_client)
        provider = (settings.LLM_PROVIDER or "groq").lower()
        if provider == "groq":
            try:
                client = GroqClient()
                return LLMQueryProvider(client=client)
            except Exception as exc:
                logger.warning(f"Could not initialize Groq client: {exc}")
                return None
        elif provider == "ollama":
            try:
                client = OllamaLLMClient()
                return LLMQueryProvider(client=client)
            except Exception as exc:
                logger.warning(f"Could not initialize Ollama client: {exc}")
                return None
        return None

    def analyze(self, query: str, context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        fast_result = self.fast_path.classify(query, context)
        if fast_result is not None:
            logger.info(f"⚡ [FAST-PATH QUERY UNDERSTANDING] Query=\"{query}\" -> Intent={fast_result['primary_intent']}")
            return fast_result

        provider_setting = (settings.QUERY_UNDERSTANDING_PROVIDER or "mock").lower()
        if provider_setting in ("llm", "hybrid"):
            llm_provider = self._get_llm_provider()
            if llm_provider is not None:
                try:
                    logger.info(f"🧠 [LLM QUERY UNDERSTANDING] Invoking LLM for query: \"{query}\"")
                    result = llm_provider.analyze(query, context)
                    result["classified_by"] = f"{settings.LLM_PROVIDER}_llm"
                    return result
                except (GroqError, OllamaError, Exception) as exc:
                    logger.warning(f"⚠️ LLM Query Understanding failed or timed out ({exc}). Falling back to rule engine.")

        fallback_result = self.mock_provider.analyze(query, context)
        fallback_result["classified_by"] = "deterministic_fallback"
        return fallback_result
