from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class BranchInfoToolInput(BaseModel):
    branch_id: Optional[str] = Field(
        default=None, description="Unique branch identifier (e.g. begur-main)"
    )
    branch_name: Optional[str] = Field(
        default=None, description="Branch or campus name (e.g. Begur Main Campus)"
    )


def get_branch_info(
    service: StructuredDataService,
    input_data: Optional[BranchInfoToolInput] = None,
) -> ToolResult:
    """
    Retrieve branch and campus location details.
    Empty input behavior: Returns list of all branch campuses.
    """
    try:
        if input_data is None:
            input_data = BranchInfoToolInput()

        # 1. Lookup by branch_id
        if input_data.branch_id and input_data.branch_id.strip():
            branch = service.get_branch_by_id(input_data.branch_id.strip())
            if not branch:
                return ToolResult(
                    tool_name="get_branch_info",
                    success=False,
                    error=f"Branch with ID '{input_data.branch_id}' not found.",
                    metadata={"source": "structured_database"},
                )
            return ToolResult(
                tool_name="get_branch_info",
                success=True,
                data=branch.model_dump(),
                metadata={"source": "structured_database"},
            )

        # 2. Lookup by branch_name (case-insensitive & whitespace normalized)
        if input_data.branch_name and input_data.branch_name.strip():
            branch = service.get_branch_by_name(input_data.branch_name.strip())
            if not branch:
                return ToolResult(
                    tool_name="get_branch_info",
                    success=False,
                    error=f"Branch with name '{input_data.branch_name}' not found.",
                    metadata={"source": "structured_database"},
                )
            return ToolResult(
                tool_name="get_branch_info",
                success=True,
                data=branch.model_dump(),
                metadata={"source": "structured_database"},
            )

        # 3. Empty input: return all branches
        branches = service.list_branches()
        return ToolResult(
            tool_name="get_branch_info",
            success=True,
            data=[b.model_dump() for b in branches],
            metadata={"source": "structured_database", "count": len(branches)},
        )

    except Exception as exc:
        return ToolResult(
            tool_name="get_branch_info",
            success=False,
            error=f"Database error executing get_branch_info: {str(exc)}",
            metadata={"source": "structured_database"},
        )
