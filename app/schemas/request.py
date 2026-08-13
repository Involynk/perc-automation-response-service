from pydantic import BaseModel, Field, field_validator


class ResponseRequest(BaseModel):
    """External API contract representing a student query request."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for student conversation session",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Student query text message",
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("session_id cannot be empty or whitespace only")
        return cleaned

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("message cannot be empty or whitespace only")
        return cleaned