from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.eligibility import EligibilityPolicyModel, ProgramEligibilityModel


class EligibilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_eligibility_policy(self) -> Optional[EligibilityPolicyModel]:
        stmt = select(EligibilityPolicyModel).where(EligibilityPolicyModel.id == 1)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_program_eligibility(self, program_name: str) -> Optional[ProgramEligibilityModel]:
        stmt = select(ProgramEligibilityModel).where(
            ProgramEligibilityModel.program_name.ilike(program_name)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_program_eligibility(self) -> List[ProgramEligibilityModel]:
        stmt = select(ProgramEligibilityModel)
        return list(self.db.execute(stmt).scalars().all())
