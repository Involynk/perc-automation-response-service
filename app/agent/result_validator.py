from typing import Any, Dict, List, Optional
import re

from pydantic import BaseModel, Field

from app.schemas.agent import AgentState, ValidationResult, ToolResult
from app.agent.generator import DraftAnswerModel


class DraftValidationResult(BaseModel):
    is_valid: bool = Field(default=True)
    is_grounded: bool = Field(default=True)
    hallucination_detected: bool = Field(default=False)
    requires_human_handoff: bool = Field(default=False)
    requires_clarification: bool = Field(default=False)
    issues: List[str] = Field(default_factory=list)
    coverage_ok: bool = Field(default=True)
    confidence_score: float = Field(default=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _extract_numbers(text: str) -> List[float]:
    nums = re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
    out = []
    for n in nums:
        try:
            out.append(float(n.replace(",", "")))
        except Exception:
            continue
    return out


def validate_draft(state: AgentState, draft: DraftAnswerModel) -> DraftValidationResult:
    """Deterministic, production-safe draft validator.

    NOTE: This validator is intentionally conservative and does NOT call any LLMs.
    It performs lightweight checks against structured tool results, RAG docs,
    and the prior `result_check` decision.
    """
    res = DraftValidationResult()

    # Basic empty/invalid draft detection
    if not draft or not getattr(draft, "draft_answer", None):
        res.is_valid = False
        res.is_grounded = False
        res.issues.append("empty_or_invalid_draft")
        res.confidence_score = 0.0
        return res

    # Enforce routing-driven clarification/handoff
    rc = getattr(state, "result_check", None)
    if rc:
        if getattr(rc, "requires_human_handoff", False):
            res.is_valid = False
            res.requires_human_handoff = True
            res.issues.append("requires_human_handoff")
            return res
        if getattr(rc, "requires_clarification", False):
            res.is_valid = False
            res.requires_clarification = True
            res.issues.append("requires_clarification")
            return res

    # Evidence availability: ensure draft references at least one evidence item if evidence was found
    if not draft.evidence or len(draft.evidence) == 0:
        if rc and getattr(rc, "has_empty_results", False):
            # No evidence was available in the database/knowledge base; safe escalation draft is expected
            res.is_grounded = True
            res.is_valid = True
            res.confidence_score = 1.0
            vr = ValidationResult(
                is_valid=True,
                is_grounded=True,
                is_safe=True,
                hallucination_detected=False,
                policy_violation=False,
                issues=[],
                confidence_score=1.0,
            )
            state.validation_result = vr
            return res

        res.is_grounded = False
        res.is_valid = False
        res.issues.append("no_evidence_in_draft")

    # Structured-data authority check: if structured evidence exists, ensure draft used it
    structured_success = 0
    for tr in getattr(state, "tool_results", []) or []:
        if isinstance(tr, ToolResult):
            name = tr.tool_name
            source = tr.metadata.get("source") if tr.metadata else None
            if source == "structured_database" or name.startswith("get_"):
                if tr.success:
                    structured_success += 1

    if structured_success > 0 and not draft.used_structured:
        res.is_valid = False
        res.is_grounded = False
        res.issues.append("structured_evidence_available_but_not_used")

    # Fee/price hallucination protection (simple heuristic)
    if state.intent and state.intent.value == "C3_FEES_PRICING":
        claimed_nums = _extract_numbers(draft.draft_answer)
        # collect structured fee amounts
        structured_amounts = []
        for tr in getattr(state, "tool_results", []) or []:
            if tr.tool_name == "get_fee" and tr.success and isinstance(tr.data, dict):
                a = tr.data.get("amount") or tr.data.get("total_fee") or tr.data.get("base_fee")
                if isinstance(a, (int, float)):
                    structured_amounts.append(float(a))

        if claimed_nums and not structured_amounts:
            res.hallucination_detected = True
            res.is_valid = False
            res.issues.append("fee_claim_without_structured_evidence")
        elif claimed_nums and structured_amounts:
            # compare first claimed number to any structured amount
            ok = any(abs(claimed_nums[0] - sa) < 0.01 * max(1.0, sa) for sa in structured_amounts)
            if not ok:
                res.hallucination_detected = True
                res.is_valid = False
                res.issues.append("fee_mismatch_with_structured_data")

    # Live-seat / availability protection
    if state.intent and state.intent.value == "C9_AVAILABILITY_STATUS":
        if re.search(r"\bseat|seats|available|capacity\b", draft.draft_answer, re.I):
            has_avail = any(tr.tool_name == "get_availability" and tr.success for tr in getattr(state, "tool_results", []) or [])
            if not has_avail:
                res.is_valid = False
                res.issues.append("availability_claim_without_structured_check")

    # Multi-intent coverage: ensure per-intent evidence is present
    if getattr(state, "secondary_intents", None):
        per = getattr(state.result_check, "per_intent_evidence", None) if state.result_check else None
        if per:
            if len(draft.evidence) < len(per):
                res.coverage_ok = False
                res.is_valid = False
                res.issues.append("multi_intent_evidence_incomplete")

    # Basic confidence scoring: downweight if issues present
    score = 1.0
    if res.issues:
        score -= 0.5
    if res.hallucination_detected:
        score -= 0.3
    if not res.is_grounded:
        score -= 0.4
    if score < 0.0:
        score = 0.0
    res.confidence_score = round(score, 3)

    # Mirror to state.validation_result as a ValidationResult for compatibility
    vr = ValidationResult(
        is_valid=res.is_valid,
        is_grounded=res.is_grounded,
        is_safe=True,
        hallucination_detected=res.hallucination_detected,
        policy_violation=False,
        issues=res.issues,
        confidence_score=res.confidence_score,
    )
    state.validation_result = vr

    # If validation found severe issues, mark human escalation
    if res.hallucination_detected or res.requires_human_handoff or not res.is_grounded:
        state.human_escalation_required = True

    return res


__all__ = ["DraftValidationResult", "validate_draft"]
