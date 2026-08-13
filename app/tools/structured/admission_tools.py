from typing import Optional
from pydantic import BaseModel

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class AdmissionStepsToolInput(BaseModel):
    pass


class AdmissionStatusToolInput(BaseModel):
    pass


def get_admission_steps(
    service: StructuredDataService,
    input_data: Optional[AdmissionStepsToolInput] = None,
) -> ToolResult:
    """
    Retrieve documented step-by-step admission process and demo class options.
    Fact Safety Enforced: No invented steps or external website calls.
    Empty input behavior: Returns complete admission process steps and policy.
    """
    try:
        policy = service.get_eligibility_policy()
        if not policy:
            return ToolResult(
                tool_name="get_admission_steps",
                success=False,
                error="Admission policy records not found.",
                metadata={"source": "structured_database"},
            )

        payload = {
            "general_policy": policy.general_policy,
            "admission_process": policy.admission_process,
            "demo_class": policy.demo_class,
        }
        return ToolResult(
            tool_name="get_admission_steps",
            success=True,
            data=payload,
            metadata={"source": "structured_database"},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="get_admission_steps",
            success=False,
            error=f"Database error executing get_admission_steps: {str(exc)}",
            metadata={"source": "structured_database"},
        )


def get_admission_status(
    service: StructuredDataService,
    input_data: Optional[AdmissionStatusToolInput] = None,
) -> ToolResult:
    """
    Retrieve current admission cycle status and batch slot information.
    Fact Safety Enforced: Reports only verified database admission status ('Open').
    Empty input behavior: Returns current status, seat limit guidelines, and contact channels.
    """
    try:
        status = service.get_admission_status()
        if not status:
            return ToolResult(
                tool_name="get_admission_status",
                success=False,
                error="Admission status records not found.",
                metadata={"source": "structured_database"},
            )

        return ToolResult(
            tool_name="get_admission_status",
            success=True,
            data=status.model_dump(),
            metadata={"source": "structured_database"},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="get_admission_status",
            success=False,
            error=f"Database error executing get_admission_status: {str(exc)}",
            metadata={"source": "structured_database"},
        )
