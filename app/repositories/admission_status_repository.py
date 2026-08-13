from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.admission_status import AdmissionStatusModel


class AdmissionStatusRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_admission_status(self) -> Optional[AdmissionStatusModel]:
        stmt = select(AdmissionStatusModel).where(AdmissionStatusModel.id == 1)
        return self.db.execute(stmt).scalar_one_or_none()
