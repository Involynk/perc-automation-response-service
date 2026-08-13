import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.admission_tools import (
    get_admission_steps,
    get_admission_status,
)


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


def test_get_admission_steps_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_admission_steps(service)
    assert res.success is True
    assert res.tool_name == "get_admission_steps"
    assert "admission_process" in res.data
    assert len(res.data["admission_process"]) == 5
    assert res.data["admission_process"][0]["title"] == "Book a Demo"
    assert res.data["demo_class"]["available"] is True


def test_get_admission_status_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_admission_status(service)
    assert res.success is True
    assert res.tool_name == "get_admission_status"
    assert res.data["current_status"] == "Open"
    assert "seat_limit_per_batch" in res.data
    assert len(res.data["batch_slots"]) >= 1


def test_get_admission_steps_service_failure():
    mock_service = MagicMock()
    mock_service.get_eligibility_policy.side_effect = Exception("DB error")
    res = get_admission_steps(mock_service)
    assert res.success is False
    assert "Database error" in res.error


def test_get_admission_status_service_failure():
    mock_service = MagicMock()
    mock_service.get_admission_status.side_effect = Exception("DB error")
    res = get_admission_status(mock_service)
    assert res.success is False
    assert "Database error" in res.error
