from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.branch import BranchModel


class BranchRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, branch_id: str) -> Optional[BranchModel]:
        if not branch_id or not branch_id.strip():
            return None
        stmt = select(BranchModel).where(BranchModel.id == branch_id.strip())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> Optional[BranchModel]:
        if not name or not name.strip():
            return None
        normalized = " ".join(name.strip().split())
        stmt = select(BranchModel).where(func.lower(BranchModel.name) == normalized.lower())
        result = self.db.execute(stmt).scalar_one_or_none()
        if not result:
            stmt = select(BranchModel).where(BranchModel.name.ilike(f"%{normalized}%"))
            result = self.db.execute(stmt).scalar_one_or_none()
        return result

    def list_branches(self) -> List[BranchModel]:
        stmt = select(BranchModel)
        return list(self.db.execute(stmt).scalars().all())
