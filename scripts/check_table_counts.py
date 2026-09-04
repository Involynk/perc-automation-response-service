import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.session import SessionLocal

tables = [
    "resp_courses",
    "resp_branches",
    "resp_fee_policies",
    "resp_program_fees",
    "resp_eligibility_policies",
    "resp_program_eligibility",
    "resp_availability_info",
    "resp_admission_status",
]

session = SessionLocal()
try:
    print("Table Record Counts in Supabase Database:")
    for tbl in tables:
        count = session.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
        print(f"{tbl}: {count}")
finally:
    session.close()
