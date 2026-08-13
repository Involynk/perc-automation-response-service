from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AvailabilityInfoModel(Base):
    """
    SQLAlchemy model representing institute timings, batch timings, and seat availability contact info.
    Derived from MockData/structured/availability.json.
    """
    __tablename__ = "resp_availability_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    institute_timings: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    batch_timings: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    one_to_one_tuition: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    contact_for_current_seat_availability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
