# Phase 5G — Draft Validation (Minimal, Production-Safe)

This document describes the minimal deterministic draft validation introduced in Phase 5G.

Goals
- Add a fast, conservative validation step after generation to catch obvious issues.
- Do NOT call any LLMs during validation.
- Keep validation deterministic and explainable.

What is implemented
- `DraftValidationResult` model (see `app/agent/result_validator.py`).
- Deterministic `validate_draft(state, draft)` performing:
  - Empty/invalid draft detection
  - Evidence availability check
  - Structured-data authority check (prefer structured evidence)
  - Fee/price hallucination protection (heuristic numeric checks)
  - Live-seat/availability protection (heuristic keyword + structured check)
  - Human-handoff and clarification enforcement (honors `result_check` flags)
  - Basic multi-intent coverage check (evidence count heuristic)
- `result_validation_node` added at `app/agent/nodes/result_validation.py` and wired into the LangGraph in `app/agent/graph.py`.
- Unit tests in `tests/agent/test_result_validation.py` using mocked data only.

Operational notes
- The validator intentionally errs on the side of escalation: when in doubt, mark the draft invalid and require human review.
- This is the minimal production-safe implementation requested — no over-engineering.

Next steps (optional)
- Add more granular evidence linking (e.g., snippet-level cross-checking).
- Implement automated claim-to-evidence matching to allow partial auto-accept.
