from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class CourseResponseSchema(BaseModel):
    id: str
    name: str
    category: str
    target_class: str
    subjects: List[str]
    focus: Optional[str] = None
    duration: str
    batch_size: Optional[str] = None
    price: Optional[str] = None
    exams_covered: List[str]
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BranchResponseSchema(BaseModel):
    id: str
    name: str
    type: str
    address: Dict[str, Any]
    geo: Optional[Dict[str, Any]] = None
    contact: Dict[str, Any]
    timings: Dict[str, Any]
    batch_slots: List[Dict[str, Any]]
    nearby_landmarks: Optional[List[str]] = None
    google_maps_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FeePolicyResponseSchema(BaseModel):
    note: Optional[str] = None
    contact_for_fees: Dict[str, Any]
    general_info: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class ProgramFeeResponseSchema(BaseModel):
    id: str
    name: str
    duration: str
    fee: str

    model_config = ConfigDict(from_attributes=True)


class EligibilityPolicyResponseSchema(BaseModel):
    general_policy: str
    admission_process: List[Dict[str, Any]]
    demo_class: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class ProgramEligibilityResponseSchema(BaseModel):
    program_name: str
    course_id: Optional[str] = None
    min_class: str
    max_class: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AvailabilityInfoResponseSchema(BaseModel):
    institute_timings: Dict[str, Any]
    batch_timings: List[Dict[str, Any]]
    one_to_one_tuition: Dict[str, Any]
    contact_for_current_seat_availability: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class AdmissionStatusResponseSchema(BaseModel):
    current_status: str
    note: Optional[str] = None
    seat_limit_per_batch: Optional[str] = None
    batch_slots: List[Dict[str, Any]]
    free_demo: Dict[str, Any]
    contact_to_check_availability: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
