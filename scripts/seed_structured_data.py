import json
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.course import CourseModel
from app.db.models.branch import BranchModel
from app.db.models.fee import FeePolicyModel, ProgramFeeModel
from app.db.models.eligibility import EligibilityPolicyModel, ProgramEligibilityModel
from app.db.models.availability import AvailabilityInfoModel
from app.db.models.admission_status import AdmissionStatusModel

MOCK_DATA_DIR = Path(__file__).resolve().parent.parent / "MockData" / "structured"


def load_json(filename: str) -> Any:
    file_path = MOCK_DATA_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"MockData file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def seed_courses(db: Session) -> Dict[str, int]:
    data = load_json("courses.json")
    inserted = 0
    updated = 0

    for item in data:
        existing = db.query(CourseModel).filter(CourseModel.id == item["id"]).first()
        if existing:
            existing.name = item["name"]
            existing.category = item["category"]
            existing.target_class = item["target_class"]
            existing.subjects = item["subjects"]
            existing.focus = item.get("focus")
            existing.duration = item["duration"]
            existing.batch_size = item.get("batch_size")
            existing.price = item.get("price")
            existing.exams_covered = item.get("exams_covered", [])
            existing.description = item.get("description")
            updated += 1
        else:
            course = CourseModel(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                target_class=item["target_class"],
                subjects=item["subjects"],
                focus=item.get("focus"),
                duration=item["duration"],
                batch_size=item.get("batch_size"),
                price=item.get("price"),
                exams_covered=item.get("exams_covered", []),
                description=item.get("description"),
            )
            db.add(course)
            inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated}


def seed_branches(db: Session) -> Dict[str, int]:
    data = load_json("branches.json")
    inserted = 0
    updated = 0

    for item in data:
        existing = db.query(BranchModel).filter(BranchModel.id == item["id"]).first()
        if existing:
            existing.name = item["name"]
            existing.type = item["type"]
            existing.address = item["address"]
            existing.geo = item.get("geo")
            existing.contact = item["contact"]
            existing.timings = item["timings"]
            existing.batch_slots = item.get("batch_slots", [])
            existing.nearby_landmarks = item.get("nearby_landmarks")
            existing.google_maps_url = item.get("google_maps_url")
            updated += 1
        else:
            branch = BranchModel(
                id=item["id"],
                name=item["name"],
                type=item["type"],
                address=item["address"],
                geo=item.get("geo"),
                contact=item["contact"],
                timings=item["timings"],
                batch_slots=item.get("batch_slots", []),
                nearby_landmarks=item.get("nearby_landmarks"),
                google_maps_url=item.get("google_maps_url"),
            )
            db.add(branch)
            inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated}


def seed_fees(db: Session) -> Dict[str, Any]:
    data = load_json("fees.json")
    
    # 1. Fee Policy Singleton
    policy_existing = db.query(FeePolicyModel).filter(FeePolicyModel.id == 1).first()
    policy_inserted = 0
    policy_updated = 0
    if policy_existing:
        policy_existing.note = data.get("note")
        policy_existing.contact_for_fees = data["contact_for_fees"]
        policy_existing.general_info = data["general_info"]
        policy_updated = 1
    else:
        policy = FeePolicyModel(
            id=1,
            note=data.get("note"),
            contact_for_fees=data["contact_for_fees"],
            general_info=data["general_info"],
        )
        db.add(policy)
        policy_inserted = 1

    # 2. Program Fees
    prog_inserted = 0
    prog_updated = 0
    for item in data.get("programs", []):
        existing = db.query(ProgramFeeModel).filter(ProgramFeeModel.id == item["id"]).first()
        if existing:
            existing.name = item["name"]
            existing.duration = item["duration"]
            existing.fee = item["fee"]
            prog_updated += 1
        else:
            prog_fee = ProgramFeeModel(
                id=item["id"],
                name=item["name"],
                duration=item["duration"],
                fee=item["fee"],
            )
            db.add(prog_fee)
            prog_inserted += 1

    db.commit()
    return {
        "policy": {"inserted": policy_inserted, "updated": policy_updated},
        "program_fees": {"inserted": prog_inserted, "updated": prog_updated},
    }


def seed_eligibility(db: Session) -> Dict[str, Any]:
    data = load_json("eligibility.json")
    
    # 1. Eligibility Policy Singleton
    policy_existing = db.query(EligibilityPolicyModel).filter(EligibilityPolicyModel.id == 1).first()
    policy_inserted = 0
    policy_updated = 0
    if policy_existing:
        policy_existing.general_policy = data["general_policy"]
        policy_existing.admission_process = data["admission_process"]
        policy_existing.demo_class = data["demo_class"]
        policy_updated = 1
    else:
        policy = EligibilityPolicyModel(
            id=1,
            general_policy=data["general_policy"],
            admission_process=data["admission_process"],
            demo_class=data["demo_class"],
        )
        db.add(policy)
        policy_inserted = 1

    # 2. Program Eligibility
    prog_inserted = 0
    prog_updated = 0
    courses_map = {c.name.lower(): c.id for c in db.query(CourseModel).all()}

    for item in data.get("program_eligibility", []):
        prog_name = item["program"]
        matched_course_id = courses_map.get(prog_name.lower())
        
        existing = db.query(ProgramEligibilityModel).filter(
            ProgramEligibilityModel.program_name == prog_name
        ).first()

        if existing:
            existing.course_id = matched_course_id
            existing.min_class = item["min_class"]
            existing.max_class = item["max_class"]
            existing.notes = item.get("notes")
            prog_updated += 1
        else:
            prog_eligibility = ProgramEligibilityModel(
                program_name=prog_name,
                course_id=matched_course_id,
                min_class=item["min_class"],
                max_class=item["max_class"],
                notes=item.get("notes"),
            )
            db.add(prog_eligibility)
            prog_inserted += 1

    db.commit()
    return {
        "policy": {"inserted": policy_inserted, "updated": policy_updated},
        "program_eligibility": {"inserted": prog_inserted, "updated": prog_updated},
    }


def seed_availability(db: Session) -> Dict[str, Any]:
    data = load_json("availability.json")
    existing = db.query(AvailabilityInfoModel).filter(AvailabilityInfoModel.id == 1).first()
    inserted = 0
    updated = 0

    if existing:
        existing.institute_timings = data["institute_timings"]
        existing.batch_timings = data["batch_timings"]
        existing.one_to_one_tuition = data["one_to_one_tuition"]
        existing.contact_for_current_seat_availability = data["contact_for_current_seat_availability"]
        updated = 1
    else:
        info = AvailabilityInfoModel(
            id=1,
            institute_timings=data["institute_timings"],
            batch_timings=data["batch_timings"],
            one_to_one_tuition=data["one_to_one_tuition"],
            contact_for_current_seat_availability=data["contact_for_current_seat_availability"],
        )
        db.add(info)
        inserted = 1

    db.commit()
    return {"inserted": inserted, "updated": updated}


def seed_admission_status(db: Session) -> Dict[str, Any]:
    data = load_json("admission-status.json")
    existing = db.query(AdmissionStatusModel).filter(AdmissionStatusModel.id == 1).first()
    inserted = 0
    updated = 0

    if existing:
        existing.current_status = data["current_status"]
        existing.note = data.get("note")
        existing.seat_limit_per_batch = data.get("seat_limit_per_batch")
        existing.batch_slots = data["batch_slots"]
        existing.free_demo = data["free_demo"]
        existing.contact_to_check_availability = data["contact_to_check_availability"]
        updated = 1
    else:
        status = AdmissionStatusModel(
            id=1,
            current_status=data["current_status"],
            note=data.get("note"),
            seat_limit_per_batch=data.get("seat_limit_per_batch"),
            batch_slots=data["batch_slots"],
            free_demo=data["free_demo"],
            contact_to_check_availability=data["contact_to_check_availability"],
        )
        db.add(status)
        inserted = 1

    db.commit()
    return {"inserted": inserted, "updated": updated}


def run_seed(session: Session = None) -> Dict[str, Any]:
    close_after = False
    if session is None:
        session = SessionLocal()
        close_after = True

    try:
        results = {
            "courses": seed_courses(session),
            "branches": seed_branches(session),
            "fees": seed_fees(session),
            "eligibility": seed_eligibility(session),
            "availability": seed_availability(session),
            "admission_status": seed_admission_status(session),
        }
        return results
    finally:
        if close_after:
            session.close()


if __name__ == "__main__":
    print("Starting idempotent structured data seeding...")
    res = run_seed()
    print("Seeding completed successfully:")
    print(json.dumps(res, indent=2))
