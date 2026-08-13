from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourseModel(Base):
    """
    SQLAlchemy model representing educational courses offered by PERC.
    Derived from MockData/structured/courses.json.
    """
    __tablename__ = "resp_courses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_class: Mapped[str] = mapped_column(String(100), nullable=False)
    subjects: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    focus: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration: Mapped[str] = mapped_column(String(50), nullable=False)
    batch_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    price: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    exams_covered: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
