from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.availability import AvailabilityInfoModel


class AvailabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_availability_info(self) -> Optional[AvailabilityInfoModel]:
        stmt = select(AvailabilityInfoModel).where(AvailabilityInfoModel.id == 1)
        return self.db.execute(stmt).scalar_one_or_none()
