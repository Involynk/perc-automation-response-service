import json
from pathlib import Path

MOCK_DATA_DIR = Path(__file__).resolve().parent.parent / "MockData" / "structured"


def test_courses_json_structure():
    file_path = MOCK_DATA_DIR / "courses.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 14
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "category" in item
        assert "target_class" in item
        assert "subjects" in item
        assert isinstance(item["subjects"], list)
        assert "duration" in item


def test_branches_json_structure():
    file_path = MOCK_DATA_DIR / "branches.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    branch = data[0]
    assert branch["id"] == "begur-main"
    assert "address" in branch
    assert "contact" in branch
    assert "timings" in branch


def test_fees_json_structure():
    file_path = MOCK_DATA_DIR / "fees.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "contact_for_fees" in data
    assert "general_info" in data
    assert "programs" in data
    assert len(data["programs"]) == 14


def test_eligibility_json_structure():
    file_path = MOCK_DATA_DIR / "eligibility.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "general_policy" in data
    assert "admission_process" in data
    assert "program_eligibility" in data
    assert len(data["program_eligibility"]) == 14


def test_availability_json_structure():
    file_path = MOCK_DATA_DIR / "availability.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "institute_timings" in data
    assert "batch_timings" in data
    assert "contact_for_current_seat_availability" in data


def test_admission_status_json_structure():
    file_path = MOCK_DATA_DIR / "admission-status.json"
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "current_status" in data
    assert "batch_slots" in data
    assert "free_demo" in data
    assert "contact_to_check_availability" in data
