from typing import Optional
from pydantic import BaseModel

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class AvailabilityToolInput(BaseModel):
    pass


def get_availability(
    service: StructuredDataService,
    input_data: Optional[AvailabilityToolInput] = None,
) -> ToolResult:
    """
    Retrieve institute operating hours, batch slot frequencies, 1-on-1 tuition schedule policies,
    and seat availability verification contact details.
    Fact Safety Enforced: Distinguishes general batch timing schedules from real-time seat availability,
    directing current seat confirmation to official phone/whatsapp channels.
    Empty input behavior: Returns institutional availability structure.
    """
    try:
        info = service.get_availability_info()
        if not info:
            return ToolResult(
                tool_name="get_availability",
                success=False,
                error="Availability records not found.",
                metadata={"source": "structured_database"},
            )

        return ToolResult(
            tool_name="get_availability",
            success=True,
            data=info.model_dump(),
            metadata={"source": "structured_database"},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="get_availability",
            success=False,
            error=f"Database error executing get_availability: {str(exc)}",
            metadata={"source": "structured_database"},
        )
