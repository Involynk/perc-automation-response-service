from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.agent import QueryIntent


class ResponseResponse(BaseModel):
    """External API response contract delivered to the student."""

    session_id: str = Field(..., description="Student conversation session ID")
    answer: str = Field(..., description="Final student-facing response message")
    status: str = Field(
        default="success",
        description="Response status (e.g., success, clarification_required, escalated, error)",
    )
    intent: Optional[QueryIntent] = Field(default=None, description="Identified query intent")
    sources: List[str] = Field(
        default_factory=list, description="User-facing source references or file names"
    )
    clarification_required: bool = Field(
        default=False, description="True if agent is asking for clarification"
    )
    clarification_question: Optional[str] = Field(
        default=None, description="Question asked to student if clarification required"
    )