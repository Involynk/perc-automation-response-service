from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BranchModel(Base):
    """
    SQLAlchemy model representing branch locations of PERC.
    Derived from MockData/structured/branches.json.
    """
    __tablename__ = "resp_branches"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geo: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    contact: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    timings: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    batch_slots: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    nearby_landmarks: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    google_maps_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
