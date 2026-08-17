# Phase 5 Integration — End-to-End Verification

This document describes the E2E verification added in Phase 5. It exercises the
complete PERC response pipeline using only deterministic MockData and injected
fake services. No real LLMs, network calls, or production DB access are performed.

Pipeline

Initialize → Query Understanding → Ambiguity → Routing → Execution → Result Check → Answer Generation → Draft Validation

Test strategy
- Use `tests/agent/query_understanding_cases.json` as the canonical set of example queries derived from `MockData/unstructured/`.
- Inject a `FakeStructuredService` that reads `MockData/structured/*.json` and provides the minimal API used by structured tools.
- Inject a `FakeRetriever` that searches `MockData/unstructured/*.md` via simple substring matching and returns `RetrievedDocument` objects.
- Monkeypatch `AnswerGenerator.generate` to a deterministic function that builds a JSON draft from available evidence. No LLMs are invoked.

Checks performed
- Verified `QueryIntent` matches expected values from the cases file.
- Verified routing decisions match `app.agent.router.decide_routing`.
- Verified structured tool results and RAG retrievals come from the fake services.
- Verified `result_check` is present and respected for generation decisions.
- Verified that generation occurs only when evidence is sufficient and that validation marks drafts as `validated` or triggers escalation when appropriate.

Limitations
- The FakeRetriever performs simple substring matching; it's sufficient for test coverage but not production-quality.
- The generator is deterministic and injected for tests; production LLM behavior remains subject to real LLM variability.
