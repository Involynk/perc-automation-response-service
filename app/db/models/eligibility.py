from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EligibilityPolicyModel(Base):
    """
    SQLAlchemy model representing general eligibility policies and admission process steps.
    Derived from MockData/structured/eligibility.json (top-level properties).
    """
    __tablename__ = "resp_eligibility_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    general_policy: Mapped[str] = mapped_column(Text, nullable=False)
    admission_process: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    demo_class: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProgramEligibilityModel(Base):
    """
    SQLAlchemy model representing program-specific eligibility requirements.
    Derived from MockData/structured/eligibility.json ("program_eligibility" array).
    """
    __tablename__ = "resp_program_eligibility"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    course_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("resp_courses.id", ondelete="SET NULL"), nullable=True
    )
    min_class: Mapped[str] = mapped_column(String(50), nullable=False)
    max_class: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
