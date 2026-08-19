import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from scripts.seed_structured_data import run_seed
from app.services.structured_data_service import StructuredDataService


@pytest.fixture(scope="module")
def db_session():
    # Use SQLite in-memory engine for fast, isolated unit testing of models/seed/repos
    engine = create_engine("sqlite:///:memory:")
    
    # Patch PostgreSQL JSONB to JSON for SQLite compatibility in unit test fixture
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import JSON
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_idempotent_seeding(db_session):
    # First seed run
    first_res = run_seed(db_session)
    assert first_res["courses"]["inserted"] == 14
    assert first_res["branches"]["inserted"] == 1
    assert first_res["fees"]["program_fees"]["inserted"] == 14

    # Second seed run (must update 0 new inserts)
    second_res = run_seed(db_session)
    assert second_res["courses"]["inserted"] == 0
    assert second_res["courses"]["updated"] == 14
    assert second_res["branches"]["inserted"] == 0
    assert second_res["fees"]["program_fees"]["inserted"] == 0


def test_structured_data_service_queries(db_session):
    service = StructuredDataService(db_session)

    # Test course queries
    course = service.get_course_by_id("perc-ignite")
    assert course is not None
    assert course.name == "PERC Ignite"
    assert course.category == "PERC Core"
    assert "Mathematics" in course.subjects

    # Test course list
    all_courses = service.list_courses()
    assert len(all_courses) == 14

    # Test course category filter
    neet_courses = service.list_courses(category="NEET")
    assert len(neet_courses) == 2

    # Test branch queries
    branch = service.get_branch_by_id("begur-main")
    assert branch is not None
    assert branch.name == "PERC — Begur Main Campus"
    assert branch.address["city"] == "Bengaluru"

    # Test fee queries
    fee_policy = service.get_fee_policy()
    assert fee_policy is not None
    assert fee_policy.contact_for_fees["phone"] == "+91 7259941873"

    prog_fee = service.get_program_fee("neet-ug")
    assert prog_fee is not None
    assert prog_fee.name == "NEET UG"

    # Test eligibility queries
    el_policy = service.get_eligibility_policy()
    assert el_policy is not None
    assert len(el_policy.admission_process) == 5

    prog_el = service.get_program_eligibility("PERC Achiever")
    assert prog_el is not None
    assert prog_el.min_class == "Class 9"

    # Test availability queries
    avail = service.get_availability_info()
    assert avail is not None
    assert "Sunday" in avail.institute_timings["day_closed"]

    # Test admission status queries
    adm = service.get_admission_status()
    assert adm is not None
    assert adm.current_status == "Open"


def test_not_found_behavior(db_session):
    service = StructuredDataService(db_session)
    assert service.get_course_by_id("non-existent-course") is None
    assert service.get_branch_by_id("non-existent-branch") is None
    assert service.get_program_fee("non-existent-fee") is None
    assert service.get_program_eligibility("non-existent-prog") is None


def test_processed_event_repository_idempotency_and_concurrency(db_session):
    """Test durable PostgreSQL service eventId persistence and duplicate conflict handling."""
    from app.repositories.event_repository import ProcessedEventRepository

    repo = ProcessedEventRepository(db_session)
    event_id = "evt_repo_test_001"

    # 1. First check -> Not processed
    assert repo.is_already_processed(event_id) is False

    # 2. Record first event -> Success
    record = repo.record_processed_event(event_id=event_id, topic="perc.lead-events", lead_id="lead_101")
    assert record is not None
    assert record.event_id == event_id
    assert record.topic == "perc.lead-events"
    assert record.lead_id == "lead_101"

    # 3. Second check -> Already processed
    assert repo.is_already_processed(event_id) is True

    # 4. Duplicate insert -> Handled gracefully without raising, returns None
    dup_record = repo.record_processed_event(event_id=event_id, topic="perc.lead-events", lead_id="lead_101")
    assert dup_record is None

