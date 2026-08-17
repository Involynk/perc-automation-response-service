import json
import os
from pathlib import Path

from app.schemas.agent import QueryIntent


CASES_PATH = Path("tests/agent/query_understanding_cases.json")


def test_cases_file_exists():
    assert CASES_PATH.exists(), f"Dataset not found at {CASES_PATH}"


def test_cases_traceable_and_schema():
    raw = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list) and len(raw) >= 18

    for case in raw:
        # basic required fields
        assert "id" in case and "query" in case and "expected_primary_intent" in case

        # source file must exist
        src = Path(case.get("source_file", ""))
        assert src.exists(), f"Source file {src} missing for case {case.get('id')}"

        # source snippet must appear in source file for traceability
        snippet = case.get("source_snippet")
        assert snippet, f"Missing source_snippet in case {case.get('id')}"
        content = src.read_text(encoding="utf-8")
        assert snippet in content, f"Snippet not found in {src} for case {case.get('id')}"

        # intent values must be valid enum values
        pri = case["expected_primary_intent"]
        assert pri in QueryIntent._value2member_map_, f"Unknown intent {pri} in case {case.get('id')}"

        # secondary intents, if any, must be valid enum values
        for s in case.get("expected_secondary_intents", []):
            assert s in QueryIntent._value2member_map_, f"Unknown secondary intent {s} in case {case.get('id')}"

        # context, if present, must be list
        assert isinstance(case.get("context", []), list)
