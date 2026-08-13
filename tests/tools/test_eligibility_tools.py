import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.eligibility_tools import get_eligibility, EligibilityToolInput


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import JSON
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    run_seed(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_get_eligibility_empty_input(db_session):
    service = StructuredDataService(db_session)
    res = get_eligibility(service)
    assert res.success is True
    assert res.tool_name == "get_eligibility"
    assert "general_policy" in res.data
    assert "program_eligibility" in res.data
    assert len(res.data["program_eligibility"]) == 14


def test_get_eligibility_by_program_name(db_session):
    service = StructuredDataService(db_session)
    res = get_eligibility(service, EligibilityToolInput(program_name="PERC Achiever"))
    assert res.success is True
    assert res.data["program_eligibility"]["program_name"] == "PERC Achiever"
    assert res.data["program_eligibility"]["min_class"] == "Class 9"


def test_get_eligibility_by_course_id(db_session):
    service = StructuredDataService(db_session)
    res = get_eligibility(service, EligibilityToolInput(course_id="neet-ug"))
    assert res.success is True
    assert res.data["program_eligibility"]["program_name"] == "NEET UG"
    assert res.data["program_eligibility"]["min_class"] == "Class 11"


def test_get_eligibility_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_eligibility(service, EligibilityToolInput(program_name="Unknown Program"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_eligibility_target_class_filter(db_session):
    service = StructuredDataService(db_session)
    res = get_eligibility(service, EligibilityToolInput(target_class="Class 6"))
    assert res.success is True
    assert len(res.data["program_eligibility"]) >= 1


def test_get_eligibility_service_failure():
    mock_service = MagicMock()
    mock_service.get_eligibility_policy.side_effect = Exception("DB Fail")
    res = get_eligibility(mock_service)
    assert res.success is False
    assert "Database error" in res.error
