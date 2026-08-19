import pytest
from app.agent.providers.hybrid_provider import DeterministicFastPathClassifier, HybridQueryUnderstandingProvider
from app.schemas.agent import QueryIntent, AgentState, ToolResult, ExtractedEntities, AmbiguityCheck
from app.agent.generator import AnswerGenerator


def test_fast_path_course_discovery():
    classifier = DeterministicFastPathClassifier()
    res = classifier.classify("What courses do you offer?")
    assert res is not None
    assert res["primary_intent"] == QueryIntent.COURSE_DISCOVERY.value
    assert res["confidence"] >= 0.90

    res2 = classifier.classify("What courses are available?")
    assert res2 is not None
    assert res2["primary_intent"] == QueryIntent.COURSE_DISCOVERY.value

    res3 = classifier.classify("List your programs")
    assert res3 is not None
    assert res3["primary_intent"] == QueryIntent.COURSE_DISCOVERY.value


def test_fast_path_course_details():
    classifier = DeterministicFastPathClassifier()
    res = classifier.classify("Tell me about PERC Ignite")
    assert res is not None
    assert res["primary_intent"] == QueryIntent.COURSE_DETAILS.value
    assert res["entities"]["program"] == "PERC Ignite"


def test_fast_path_fee_with_course():
    classifier = DeterministicFastPathClassifier()
    res = classifier.classify("What is the fee for NEET UG?")
    assert res is not None
    assert res["primary_intent"] == QueryIntent.FEES_PRICING.value
    assert res["entities"]["program"] == "NEET UG"


def test_fast_path_fee_ambiguous_without_course():
    classifier = DeterministicFastPathClassifier()
    res = classifier.classify("What is the fee?")
    assert res is not None
    assert res["primary_intent"] == QueryIntent.AMBIGUOUS_INCOMPLETE.value
    assert res["ambiguity"]["is_ambiguous"] is True
    assert res["ambiguity"]["clarification_required"] is True


def test_fast_path_greeting():
    classifier = DeterministicFastPathClassifier()
    res = classifier.classify("Hello")
    assert res is not None
    assert res["primary_intent"] == QueryIntent.AMBIGUOUS_INCOMPLETE.value
    assert res["ambiguity"]["clarification_required"] is True


def test_answer_generator_course_discovery_formatting():
    gen = AnswerGenerator()
    state = AgentState(
        session_id="s1",
        query="What courses do you offer?",
        intent=QueryIntent.COURSE_DISCOVERY,
        tool_results=[
            ToolResult(
                tool_name="get_course_info",
                success=True,
                data=[
                    {"name": "PERC Ignite", "target_class": "Class 6"},
                    {"name": "NEET UG", "target_class": "Classes 11-12"},
                ],
                metadata={"source": "structured_database"},
            )
        ],
    )
    draft = gen.generate(state)
    assert draft.used_structured is True
    assert "PERC Ignite" in draft.draft_answer
    assert "NEET UG" in draft.draft_answer
    assert draft.confidence == 1.0


def test_answer_generator_fee_formatting():
    gen = AnswerGenerator()
    state = AgentState(
        session_id="s2",
        query="What is the fee for NEET UG?",
        intent=QueryIntent.FEES_PRICING,
        tool_results=[
            ToolResult(
                tool_name="get_fee",
                success=True,
                data={"course_name": "NEET UG", "amount": 85000, "installments": "3 installments"},
                metadata={"source": "structured_database"},
            )
        ],
    )
    draft = gen.generate(state)
    assert draft.used_structured is True
    assert "₹85,000" in draft.draft_answer
    assert "3 installments" in draft.draft_answer
