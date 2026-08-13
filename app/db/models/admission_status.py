from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdmissionStatusModel(Base):
    """
    SQLAlchemy model representing admission status and free demo class options.
    Derived from MockData/structured/admission-status.json.
    """
    __tablename__ = "resp_admission_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seat_limit_per_batch: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    batch_slots: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    free_demo: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    contact_to_check_availability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
