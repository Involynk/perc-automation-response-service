import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.fee_tools import get_fee, FeeToolInput


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


def test_get_fee_empty_input(db_session):
    service = StructuredDataService(db_session)
    res = get_fee(service)
    assert res.success is True
    assert res.tool_name == "get_fee"
    assert "fee_policy" in res.data
    assert "programs" in res.data
    assert len(res.data["programs"]) == 14


def test_get_fee_valid_course_id(db_session):
    service = StructuredDataService(db_session)
    res = get_fee(service, FeeToolInput(course_id="perc-ignite"))
    assert res.success is True
    assert res.data["program_fee"]["name"] == "PERC Ignite"
    # Verify fee safety rule: stored indicator "Contact for price", no fabricated numbers
    assert res.data["program_fee"]["fee"] == "Contact for price"
    assert "contact_for_fees" in res.data
    assert res.data["contact_for_fees"]["phone"] == "+91 7259941873"


def test_get_fee_valid_course_name(db_session):
    service = StructuredDataService(db_session)
    res = get_fee(service, FeeToolInput(course_name="IIT-JEE Advanced"))
    assert res.success is True
    assert res.data["program_fee"]["name"] == "IIT-JEE Advanced"
    assert res.data["program_fee"]["fee"] == "Contact for price"


def test_get_fee_course_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_fee(service, FeeToolInput(course_id="invalid-course"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_fee_service_failure():
    mock_service = MagicMock()
    mock_service.get_fee_policy.side_effect = Exception("Database failure")
    res = get_fee(mock_service)
    assert res.success is False
    assert "Database error" in res.error
