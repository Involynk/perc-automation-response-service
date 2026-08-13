from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.fee import FeePolicyModel, ProgramFeeModel


class FeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_fee_policy(self) -> Optional[FeePolicyModel]:
        stmt = select(FeePolicyModel).where(FeePolicyModel.id == 1)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_program_fee(self, course_id: str) -> Optional[ProgramFeeModel]:
        stmt = select(ProgramFeeModel).where(ProgramFeeModel.id == course_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_program_fees(self) -> List[ProgramFeeModel]:
        stmt = select(ProgramFeeModel)
        return list(self.db.execute(stmt).scalars().all())
