from app.schemas.agent import AgentState
from app.agent.result_validator import validate_draft
from app.agent.generator import DraftAnswerModel


def result_validation_node(state: AgentState) -> AgentState:
    """Phase 5G result_validation node: deterministic draft validation.

    This node must NOT call any LLMs. It performs conservative checks on the
    `state.draft_answer` (already validated as JSON by the generator) and
    populates `state.validation_result` and `state.human_escalation_required`.
    """
    state.metadata = dict(state.metadata or {})

    if not getattr(state, "draft_answer", None):
        # Nothing to validate; create a failed validation result
        state.validation_result = None
        state.human_escalation_required = True
        state.metadata["validation_status"] = "no_draft_to_validate"
        return state

    # state.draft_answer may be a JSON string or already the DraftAnswerModel
    draft = None
    if isinstance(state.draft_answer, DraftAnswerModel):
        draft = state.draft_answer
    else:
        # Try to construct DraftAnswerModel; generator should have ensured this
        try:
            if isinstance(state.draft_answer, str):
                import json

                parsed = json.loads(state.draft_answer)
            else:
                parsed = state.draft_answer
            draft = DraftAnswerModel(**parsed)
        except Exception:
            # mark invalid and escalate
            state.validation_result = None
            state.human_escalation_required = True
            state.metadata["validation_status"] = "draft_parse_failure"
            return state

    # Run deterministic validator
    dv = validate_draft(state, draft)

    state.metadata["validation_status"] = "validated"
    state.metadata["validation_confidence"] = float(dv.confidence_score)

    return state


__all__ = ["result_validation_node"]
