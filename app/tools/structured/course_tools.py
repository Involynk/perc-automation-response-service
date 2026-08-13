from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.agent import ToolResult
from app.services.structured_data_service import StructuredDataService


class CourseInfoToolInput(BaseModel):
    course_id: Optional[str] = Field(
        default=None, description="Unique course identifier (e.g. perc-ignite, neet-ug)"
    )
    course_name: Optional[str] = Field(
        default=None, description="Course or program name (e.g. PERC Ignite, NEET UG)"
    )
    target_class: Optional[str] = Field(
        default=None, description="Target grade or class (e.g. Class 6, Class 9, Classes 11-12)"
    )
    category: Optional[str] = Field(
        default=None, description="Course category (e.g. PERC Core, NEET, JEE, KCET, CBSE, ICSE)"
    )
    exam: Optional[str] = Field(
        default=None, description="Target exam covered (e.g. CBSE, ICSE, NEET, JEE Main, KCET)"
    )


def get_course_info(
    service: StructuredDataService,
    input_data: Optional[CourseInfoToolInput] = None,
) -> ToolResult:
    """
    Retrieve structured course and program information from the database.
    Empty input behavior: Returns all 14 courses.
    """
    try:
        if input_data is None:
            input_data = CourseInfoToolInput()

        # 1. Lookup by course_id if provided
        if input_data.course_id and input_data.course_id.strip():
            course = service.get_course_by_id(input_data.course_id.strip())
            if not course:
                return ToolResult(
                    tool_name="get_course_info",
                    success=False,
                    error=f"Course with ID '{input_data.course_id}' not found.",
                    metadata={"source": "structured_database"},
                )
            return ToolResult(
                tool_name="get_course_info",
                success=True,
                data=course.model_dump(),
                metadata={"source": "structured_database"},
            )

        # 2. Lookup by course_name if provided
        if input_data.course_name and input_data.course_name.strip():
            course = service.get_course_by_name(input_data.course_name.strip())
            if not course:
                return ToolResult(
                    tool_name="get_course_info",
                    success=False,
                    error=f"Course with name '{input_data.course_name}' not found.",
                    metadata={"source": "structured_database"},
                )
            return ToolResult(
                tool_name="get_course_info",
                success=True,
                data=course.model_dump(),
                metadata={"source": "structured_database"},
            )

        # 3. Filter/List courses by parameters or return all courses if empty input
        courses = service.list_courses(
            category=input_data.category,
            target_class=input_data.target_class,
            exam=input_data.exam,
        )
        return ToolResult(
            tool_name="get_course_info",
            success=True,
            data=[c.model_dump() for c in courses],
            metadata={"source": "structured_database", "count": len(courses)},
        )

    except Exception as exc:
        return ToolResult(
            tool_name="get_course_info",
            success=False,
            error=f"Database error executing get_course_info: {str(exc)}",
            metadata={"source": "structured_database"},
        )
