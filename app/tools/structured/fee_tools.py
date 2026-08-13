from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class FeeToolInput(BaseModel):
    course_id: Optional[str] = Field(
        default=None, description="Unique course identifier (e.g. perc-ignite, neet-ug)"
    )
    course_name: Optional[str] = Field(
        default=None, description="Course or program name (e.g. PERC Ignite, NEET UG)"
    )


def get_fee(
    service: StructuredDataService,
    input_data: Optional[FeeToolInput] = None,
) -> ToolResult:
    """
    Retrieve fee information for PERC programs and institutional fee policy.
    Fact Safety Enforced: Never invents numeric prices, discounts, or EMI plans.
    Empty input behavior: Returns global fee policy and list of all program fee records.
    """
    try:
        if input_data is None:
            input_data = FeeToolInput()

        fee_policy = service.get_fee_policy()
        policy_dict = fee_policy.model_dump() if fee_policy else {}

        # 1. Lookup specific course fee if course_id or course_name is provided
        target_course_id = None
        if input_data.course_id and input_data.course_id.strip():
            course = service.get_course_by_id(input_data.course_id.strip())
            if not course:
                return ToolResult(
                    tool_name="get_fee",
                    success=False,
                    error=f"Course with ID '{input_data.course_id}' not found.",
                    metadata={"source": "structured_database"},
                )
            target_course_id = course.id
        elif input_data.course_name and input_data.course_name.strip():
            course = service.get_course_by_name(input_data.course_name.strip())
            if not course:
                return ToolResult(
                    tool_name="get_fee",
                    success=False,
                    error=f"Course with name '{input_data.course_name}' not found.",
                    metadata={"source": "structured_database"},
                )
            target_course_id = course.id

        if target_course_id:
            prog_fee = service.get_program_fee(target_course_id)
            if not prog_fee:
                return ToolResult(
                    tool_name="get_fee",
                    success=False,
                    error=f"Fee record for course '{target_course_id}' not found.",
                    metadata={"source": "structured_database"},
                )
            payload = {
                "program_fee": prog_fee.model_dump(),
                "policy_note": policy_dict.get("note"),
                "contact_for_fees": policy_dict.get("contact_for_fees"),
                "general_info": policy_dict.get("general_info"),
            }
            return ToolResult(
                tool_name="get_fee",
                success=True,
                data=payload,
                metadata={"source": "structured_database"},
            )

        # 2. Empty input: return all program fees + global policy
        all_prog_fees = service.list_program_fees()
        payload = {
            "fee_policy": policy_dict,
            "programs": [pf.model_dump() for pf in all_prog_fees],
        }
        return ToolResult(
            tool_name="get_fee",
            success=True,
            data=payload,
            metadata={"source": "structured_database", "count": len(all_prog_fees)},
        )

    except Exception as exc:
        return ToolResult(
            tool_name="get_fee",
            success=False,
            error=f"Database error executing get_fee: {str(exc)}",
            metadata={"source": "structured_database"},
        )
