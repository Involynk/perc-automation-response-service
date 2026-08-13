import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.branch_tools import get_branch_info, BranchInfoToolInput


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


def test_get_branch_info_empty_input(db_session):
    service = StructuredDataService(db_session)
    res = get_branch_info(service)
    assert res.success is True
    assert res.tool_name == "get_branch_info"
    assert isinstance(res.data, list)
    assert len(res.data) == 1
    assert res.data[0]["id"] == "begur-main"


def test_get_branch_info_by_id_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_branch_info(service, BranchInfoToolInput(branch_id="begur-main"))
    assert res.success is True
    assert res.data["name"] == "PERC — Begur Main Campus"
    assert res.data["address"]["area"] == "Begur"


def test_get_branch_info_by_id_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_branch_info(service, BranchInfoToolInput(branch_id="unknown-branch"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_branch_info_by_name_normalized(db_session):
    service = StructuredDataService(db_session)
    # Test case-insensitive and normalized whitespace matching
    res = get_branch_info(service, BranchInfoToolInput(branch_name="  perc — begur main campus  "))
    assert res.success is True
    assert res.data["id"] == "begur-main"


def test_get_branch_info_by_name_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_branch_info(service, BranchInfoToolInput(branch_name="Koramangala Branch"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_branch_info_service_failure():
    mock_service = MagicMock()
    mock_service.list_branches.side_effect = Exception("DB error")
    res = get_branch_info(mock_service)
    assert res.success is False
    assert "Database error" in res.error
