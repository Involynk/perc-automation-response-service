from typing import List, Optional
from sqlalchemy import Text, func, select
from sqlalchemy.orm import Session

from app.db.models.course import CourseModel


class CourseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, course_id: str) -> Optional[CourseModel]:
        if not course_id or not course_id.strip():
            return None
        stmt = select(CourseModel).where(CourseModel.id == course_id.strip())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> Optional[CourseModel]:
        if not name or not name.strip():
            return None
        normalized = " ".join(name.strip().split())
        stmt = select(CourseModel).where(func.lower(CourseModel.name) == normalized.lower())
        result = self.db.execute(stmt).scalar_one_or_none()
        if not result:
            stmt = select(CourseModel).where(CourseModel.name.ilike(f"%{normalized}%"))
            result = self.db.execute(stmt).scalar_one_or_none()
        return result

    def list_courses(
        self,
        category: Optional[str] = None,
        target_class: Optional[str] = None,
        exam: Optional[str] = None,
    ) -> List[CourseModel]:
        stmt = select(CourseModel)
        if category and category.strip():
            stmt = stmt.where(CourseModel.category.ilike(category.strip()))
        if target_class and target_class.strip():
            stmt = stmt.where(CourseModel.target_class.ilike(f"%{target_class.strip()}%"))
        if exam and exam.strip():
            stmt = stmt.where(CourseModel.exams_covered.cast(Text).ilike(f"%{exam.strip()}%"))
        return list(self.db.execute(stmt).scalars().all())
