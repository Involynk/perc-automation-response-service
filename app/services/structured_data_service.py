from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.course_repository import CourseRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.eligibility_repository import EligibilityRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.admission_status_repository import AdmissionStatusRepository

from app.schemas.structured import (
    CourseResponseSchema,
    BranchResponseSchema,
    FeePolicyResponseSchema,
    ProgramFeeResponseSchema,
    EligibilityPolicyResponseSchema,
    ProgramEligibilityResponseSchema,
    AvailabilityInfoResponseSchema,
    AdmissionStatusResponseSchema,
)


class StructuredDataService:
    """
    Coordinates structured knowledge layer repositories and converts database models
    into clean Pydantic domain models.
    """
    def __init__(self, db: Session):
        self.db = db
        self.course_repo = CourseRepository(db)
        self.branch_repo = BranchRepository(db)
        self.fee_repo = FeeRepository(db)
        self.eligibility_repo = EligibilityRepository(db)
        self.availability_repo = AvailabilityRepository(db)
        self.admission_status_repo = AdmissionStatusRepository(db)

    def get_course_by_id(self, course_id: str) -> Optional[CourseResponseSchema]:
        course = self.course_repo.get_by_id(course_id)
        return CourseResponseSchema.model_validate(course) if course else None

    def get_course_by_name(self, name: str) -> Optional[CourseResponseSchema]:
        course = self.course_repo.get_by_name(name)
        return CourseResponseSchema.model_validate(course) if course else None

    def list_courses(
        self,
        category: Optional[str] = None,
        target_class: Optional[str] = None,
        exam: Optional[str] = None,
    ) -> List[CourseResponseSchema]:
        courses = self.course_repo.list_courses(category, target_class, exam)
        return [CourseResponseSchema.model_validate(c) for c in courses]

    def get_branch_by_id(self, branch_id: str) -> Optional[BranchResponseSchema]:
        branch = self.branch_repo.get_by_id(branch_id)
        return BranchResponseSchema.model_validate(branch) if branch else None

    def get_branch_by_name(self, name: str) -> Optional[BranchResponseSchema]:
        branch = self.branch_repo.get_by_name(name)
        return BranchResponseSchema.model_validate(branch) if branch else None

    def list_branches(self) -> List[BranchResponseSchema]:
        branches = self.branch_repo.list_branches()
        return [BranchResponseSchema.model_validate(b) for b in branches]

    def get_fee_policy(self) -> Optional[FeePolicyResponseSchema]:
        policy = self.fee_repo.get_fee_policy()
        return FeePolicyResponseSchema.model_validate(policy) if policy else None

    def get_program_fee(self, course_id: str) -> Optional[ProgramFeeResponseSchema]:
        fee = self.fee_repo.get_program_fee(course_id)
        return ProgramFeeResponseSchema.model_validate(fee) if fee else None

    def list_program_fees(self) -> List[ProgramFeeResponseSchema]:
        fees = self.fee_repo.list_program_fees()
        return [ProgramFeeResponseSchema.model_validate(f) for f in fees]

    def get_eligibility_policy(self) -> Optional[EligibilityPolicyResponseSchema]:
        policy = self.eligibility_repo.get_eligibility_policy()
        return EligibilityPolicyResponseSchema.model_validate(policy) if policy else None

    def get_program_eligibility(self, program_name: str) -> Optional[ProgramEligibilityResponseSchema]:
        el = self.eligibility_repo.get_program_eligibility(program_name)
        return ProgramEligibilityResponseSchema.model_validate(el) if el else None

    def list_program_eligibilities(self) -> List[ProgramEligibilityResponseSchema]:
        els = self.eligibility_repo.list_program_eligibility()
        return [ProgramEligibilityResponseSchema.model_validate(e) for e in els]

    def get_availability_info(self) -> Optional[AvailabilityInfoResponseSchema]:
        info = self.availability_repo.get_availability_info()
        return AvailabilityInfoResponseSchema.model_validate(info) if info else None

    def get_admission_status(self) -> Optional[AdmissionStatusResponseSchema]:
        status = self.admission_status_repo.get_admission_status()
        return AdmissionStatusResponseSchema.model_validate(status) if status else None
