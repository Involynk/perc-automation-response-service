import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.availability_tools import get_availability


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


def test_get_availability_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_availability(service)
    assert res.success is True
    assert res.tool_name == "get_availability"
    assert "institute_timings" in res.data
    assert "batch_timings" in res.data
    assert "one_to_one_tuition" in res.data
    # Fact safety check: verifies seat contact channels exist without inventing real-time seat numbers
    assert "contact_for_current_seat_availability" in res.data
    assert res.data["contact_for_current_seat_availability"]["phone"] == "+91 7259941873"


def test_get_availability_service_failure():
    mock_service = MagicMock()
    mock_service.get_availability_info.side_effect = Exception("DB Fail")
    res = get_availability(mock_service)
    assert res.success is False
    assert "Database error" in res.error
