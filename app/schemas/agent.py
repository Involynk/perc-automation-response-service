from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QueryIntent(str, Enum):
    """Intent categories defined in PERC research and dataset."""

    COURSE_DISCOVERY = "C1_COURSE_DISCOVERY"
    COURSE_DETAILS = "C2_COURSE_DETAILS"
    FEES_PRICING = "C3_FEES_PRICING"
    ELIGIBILITY = "C4_ELIGIBILITY"
    BRANCH_LOCATION = "C5_BRANCH_LOCATION"
    ADMISSION_PROCESS = "C6_ADMISSION_PROCESS"
    REQUIRED_DOCUMENTS = "C7_REQUIRED_DOCUMENTS"
    POLICIES = "C8_POLICIES"
    AVAILABILITY_STATUS = "C9_AVAILABILITY_STATUS"
    COMPARISON = "C10_COMPARISON"
    MULTI_INTENT = "C11_MULTI_INTENT"
    FOLLOW_UP_CONTEXTUAL = "C12_FOLLOW_UP_CONTEXTUAL"
    AMBIGUOUS_INCOMPLETE = "C13_AMBIGUOUS_INCOMPLETE"
    OUT_OF_SCOPE_ESCALATION = "C14_OUT_OF_SCOPE_ESCALATION"
    GRIEVANCE_HUMAN_HANDOFF = "C15_GRIEVANCE_HUMAN_HANDOFF"
    HOSTEL_ACCOMMODATION = "C16_HOSTEL_ACCOMMODATION"
    PLACEMENT_CAREER_OUTCOMES = "C17_PLACEMENT_CAREER_OUTCOMES"
    LANGUAGE_MEDIUM = "C18_LANGUAGE_MEDIUM"


class ExtractedEntities(BaseModel):
    """Extensible representation for query-extracted entities."""

    model_config = ConfigDict(populate_by_name=True)

    course: Optional[str] = Field(default=None, description="Course or program name")
    branch: Optional[str] = Field(default=None, description="Branch or campus name")
    program: Optional[str] = Field(default=None, description="Broad program type/category")
    exam: Optional[str] = Field(default=None, description="Target exam (e.g. JEE, NEET, KCET)")
    target_class: Optional[str] = Field(default=None, alias="class", description="Target grade/class")
    category: Optional[str] = Field(default=None, description="Subject or program category")
    location: Optional[str] = Field(default=None, description="Geographic location or area")
    academic_year: Optional[str] = Field(default=None, description="Academic year or session")
    additional_entities: Dict[str, Any] = Field(
        default_factory=dict, description="Extensible key-value pairs for other entities"
    )


class AmbiguityCheck(BaseModel):
    """Data contract representing query ambiguity evaluation."""

    is_ambiguous: bool = Field(default=False, description="True if query lacks essential parameters")
    missing_information: List[str] = Field(
        default_factory=list, description="List of missing parameters required for resolution"
    )
    clarification_required: bool = Field(
        default=False, description="Whether agent should pause and ask clarification"
    )
    clarification_question: Optional[str] = Field(
        default=None, description="Generated question to ask student for clarification"
    )


class ToolSelection(BaseModel):
    """Contract representing a tool invocation selected by the agent."""

    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool execution")
    reason: Optional[str] = Field(default=None, description="Rationale for selecting this tool")
    execution_order: int = Field(default=1, ge=1, description="Order of tool execution")


class ToolResult(BaseModel):
    """Generic contract representing the output of a tool execution."""

    tool_name: str = Field(..., description="Name of the executed tool")
    success: bool = Field(..., description="Execution status")
    data: Optional[Any] = Field(default=None, description="Returned payload data")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Tool execution metadata")


class RetrievedDocument(BaseModel):
    """Schema representing a retrieved document chunk for RAG context."""

    doc_id: Optional[str] = Field(default=None, description="Unique document ID")
    chunk_id: Optional[str] = Field(default=None, description="Chunk ID within document")
    source_file: str = Field(..., description="Source filename or URI")
    content: str = Field(..., description="Raw text content of the chunk")
    relevance_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Similarity or relevance score"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class ValidationResult(BaseModel):
    """Contract representing evaluation of the generated draft answer."""

    is_valid: bool = Field(default=True, description="Overall answer validity")
    is_grounded: bool = Field(default=True, description="Whether answer is supported by retrieved data")
    is_safe: bool = Field(default=True, description="Safety and policy compliance")
    hallucination_detected: bool = Field(default=False, description="True if ungrounded claims detected")
    policy_violation: bool = Field(default=False, description="True if forbidden content detected")
    issues: List[str] = Field(default_factory=list, description="List of detected validation issues")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall confidence score")


class AgentState(BaseModel):
    """Central internal agent state contract shared across execution lifecycle nodes."""

    session_id: str = Field(..., description="Student session ID")
    query: str = Field(..., description="Original raw user query")
    intent: Optional[QueryIntent] = Field(default=None, description="Primary detected intent")
    secondary_intents: List[QueryIntent] = Field(
        default_factory=list, description="Secondary intents for multi-intent queries"
    )
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities, description="Extracted domain entities"
    )
    ambiguity: AmbiguityCheck = Field(
        default_factory=AmbiguityCheck, description="Ambiguity evaluation status"
    )
    selected_tools: List[ToolSelection] = Field(
        default_factory=list, description="List of tools selected for execution"
    )
    tool_results: List[ToolResult] = Field(
        default_factory=list, description="Results from tool executions"
    )
    retrieved_documents: List[RetrievedDocument] = Field(
        default_factory=list, description="Documents retrieved via RAG"
    )
    draft_answer: Optional[str] = Field(default=None, description="Unvalidated LLM generated draft answer")
    validation_result: Optional[ValidationResult] = Field(
        default=None, description="Answer validation report"
    )
    final_answer: Optional[str] = Field(default=None, description="Validated final answer to user")
    human_escalation_required: bool = Field(
        default=False, description="Whether query requires human intervention"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session and execution metadata")
    # Result check produced in Phase 5E prior to answer generation
    result_check: Optional[Any] = Field(default=None, description="Structured result check and evidence summary")