import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService
from app.tools.structured.course_tools import get_course_info, CourseInfoToolInput


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


def test_get_course_info_empty_input(db_session):
    service = StructuredDataService(db_session)
    res = get_course_info(service)
    assert res.success is True
    assert res.tool_name == "get_course_info"
    assert isinstance(res.data, list)
    assert len(res.data) == 14
    assert res.metadata["count"] == 14


def test_get_course_info_by_id_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_course_info(service, CourseInfoToolInput(course_id="perc-ignite"))
    assert res.success is True
    assert res.data["name"] == "PERC Ignite"
    assert res.data["target_class"] == "Class 6"


def test_get_course_info_by_id_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_course_info(service, CourseInfoToolInput(course_id="unknown-course-xyz"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_course_info_by_name_valid(db_session):
    service = StructuredDataService(db_session)
    res = get_course_info(service, CourseInfoToolInput(course_name="NEET UG"))
    assert res.success is True
    assert res.data["id"] == "neet-ug"


def test_get_course_info_by_name_not_found(db_session):
    service = StructuredDataService(db_session)
    res = get_course_info(service, CourseInfoToolInput(course_name="Non Existent Program"))
    assert res.success is False
    assert "not found" in res.error.lower()


def test_get_course_info_filters(db_session):
    service = StructuredDataService(db_session)
    
    # Filter by category
    res_cat = get_course_info(service, CourseInfoToolInput(category="NEET"))
    assert res_cat.success is True
    assert len(res_cat.data) == 2

    # Filter by target_class
    res_class = get_course_info(service, CourseInfoToolInput(target_class="Class 9"))
    assert res_class.success is True
    assert len(res_class.data) >= 1

    # Filter by exam
    res_exam = get_course_info(service, CourseInfoToolInput(exam="JEE Advanced"))
    assert res_exam.success is True
    assert len(res_exam.data) == 1
    assert res_exam.data[0]["id"] == "iit-jee-advanced"


def test_get_course_info_service_failure():
    mock_service = MagicMock()
    mock_service.list_courses.side_effect = Exception("Database connection timeout")
    res = get_course_info(mock_service)
    assert res.success is False
    assert "Database error" in res.error
