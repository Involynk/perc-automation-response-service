from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class EligibilityToolInput(BaseModel):
    course_id: Optional[str] = Field(
        default=None, description="Unique course identifier (e.g. perc-ignite, neet-ug)"
    )
    program_name: Optional[str] = Field(
        default=None, description="Program name (e.g. PERC Ignite, NEET UG, One-to-One Tuition)"
    )
    target_class: Optional[str] = Field(
        default=None, description="Target class/grade to filter eligibility"
    )


def get_eligibility(
    service: StructuredDataService,
    input_data: Optional[EligibilityToolInput] = None,
) -> ToolResult:
    """
    Retrieve eligibility policy requirements for PERC academic programs.
    Empty input behavior: Returns general policy and list of all program eligibility requirements.
    """
    try:
        if input_data is None:
            input_data = EligibilityToolInput()

        policy = service.get_eligibility_policy()
        policy_dict = policy.model_dump() if policy else {}

        search_name = None
        if input_data.program_name and input_data.program_name.strip():
            search_name = input_data.program_name.strip()
        elif input_data.course_id and input_data.course_id.strip():
            course = service.get_course_by_id(input_data.course_id.strip())
            if course:
                search_name = course.name
            else:
                return ToolResult(
                    tool_name="get_eligibility",
                    success=False,
                    error=f"Course with ID '{input_data.course_id}' not found.",
                    metadata={"source": "structured_database"},
                )

        # 1. Specific program lookup
        if search_name:
            prog_el = service.get_program_eligibility(search_name)
            if not prog_el:
                return ToolResult(
                    tool_name="get_eligibility",
                    success=False,
                    error=f"Eligibility info for program '{search_name}' not found.",
                    metadata={"source": "structured_database"},
                )
            payload = {
                "general_policy": policy_dict.get("general_policy"),
                "program_eligibility": prog_el.model_dump(),
            }
            return ToolResult(
                tool_name="get_eligibility",
                success=True,
                data=payload,
                metadata={"source": "structured_database"},
            )

        # 2. Empty input / Filter by target_class
        all_els = service.list_program_eligibilities()
        if input_data.target_class and input_data.target_class.strip():
            cls_str = input_data.target_class.strip().lower()
            all_els = [
                e for e in all_els
                if cls_str in e.min_class.lower() or cls_str in e.max_class.lower() or e.min_class.lower() == "any"
            ]

        payload = {
            "general_policy": policy_dict.get("general_policy"),
            "program_eligibility": [e.model_dump() for e in all_els],
        }
        return ToolResult(
            tool_name="get_eligibility",
            success=True,
            data=payload,
            metadata={"source": "structured_database", "count": len(all_els)},
        )

    except Exception as exc:
        return ToolResult(
            tool_name="get_eligibility",
            success=False,
            error=f"Database error executing get_eligibility: {str(exc)}",
            metadata={"source": "structured_database"},
        )
