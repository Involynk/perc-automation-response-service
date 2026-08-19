import pytest
from app.agent.composer import ResponseComposer, NormalizedResult
from app.schemas.agent import QueryIntent, AgentState, ToolResult


def test_composer_course_discovery():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.COURSE_DISCOVERY,
        structured_list=[{"name": "PERC Ignite"}, {"name": "NEET UG"}],
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "Available Programs:" in ans
    assert "PERC Ignite" in ans
    assert "Which class or exam are you preparing for?" in ans


def test_composer_course_details():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.COURSE_DETAILS,
        structured_data={
            "name": "PERC Ignite",
            "target_class": "Class 6",
            "duration": "1 Year",
            "subjects": ["Mathematics", "Science"],
            "focus": "Conceptual foundations",
            "description": "Designed for class 6 students.",
        },
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "**PERC Ignite**" in ans
    assert "Class 6" in ans
    assert "1 Year" in ans
    assert "Mathematics, Science" in ans


def test_composer_fee_contact_for_price():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.FEES_PRICING,
        structured_data={
            "program_fee": {
                "name": "NEET UG",
                "duration": "2 Years",
                "fee": "Contact for price",
            }
        },
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "**NEET UG**" in ans
    assert "Contact admissions for current pricing" in ans


def test_composer_fee_numeric():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.FEES_PRICING,
        structured_data={
            "course_name": "NEET Crash Course",
            "amount": 45000,
            "installments": "2 installments",
        },
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "₹45,000" in ans
    assert "2 installments" in ans


def test_composer_branch_location():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.BRANCH_LOCATION,
        structured_list=[
            {
                "name": "Ujire Center",
                "address": {"full_address": "Main Road, Ujire, Karnataka 574240"},
                "contact": {"phone": "+91 9876543210"},
            }
        ],
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "Ujire Center" in ans
    assert "+91 9876543210" in ans


def test_composer_eligibility():
    composer = ResponseComposer()
    nr = NormalizedResult(
        intent=QueryIntent.ELIGIBILITY,
        structured_data={
            "program_name": "PERC Champion",
            "min_class": "Class 10",
            "max_class": "Class 10",
        },
        data_available=True,
    )
    ans = composer.compose(nr)
    assert "Eligibility for PERC Champion" in ans
    assert "Class 10" in ans


def test_composer_admission_process():
    composer = ResponseComposer()
    nr = NormalizedResult(intent=QueryIntent.ADMISSION_PROCESS, data_available=True)
    ans = composer.compose(nr)
    assert "PERC Admission Steps:" in ans
    assert "Enquiry & Counseling" in ans


def test_composer_greeting_ambiguous():
    composer = ResponseComposer()
    nr = NormalizedResult(intent=QueryIntent.AMBIGUOUS_INCOMPLETE, query="Hello")
    ans = composer.compose(nr)
    assert "Hello! 👋" in ans


def test_composer_unavailable_fallback():
    composer = ResponseComposer()
    nr = NormalizedResult(intent=QueryIntent.COURSE_DETAILS, data_available=False)
    ans = composer.compose(nr)
    assert "unable to find sufficient details" in ans
