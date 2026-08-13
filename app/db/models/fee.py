from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeePolicyModel(Base):
    """
    SQLAlchemy model representing global fee policies and contact info.
    Derived from MockData/structured/fees.json (top-level properties).
    """
    __tablename__ = "resp_fee_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_for_fees: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    general_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProgramFeeModel(Base):
    """
    SQLAlchemy model representing program-specific fee information.
    Derived from MockData/structured/fees.json ("programs" array).
    """
    __tablename__ = "resp_program_fees"

    id: Mapped[str] = mapped_column(
        String(50), ForeignKey("resp_courses.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration: Mapped[str] = mapped_column(String(50), nullable=False)
    fee: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
