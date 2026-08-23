from app.db.models.course import CourseModel
from app.db.models.branch import BranchModel
from app.db.models.fee import FeePolicyModel, ProgramFeeModel
from app.db.models.eligibility import EligibilityPolicyModel, ProgramEligibilityModel
from app.db.models.availability import AvailabilityInfoModel
from app.db.models.admission_status import AdmissionStatusModel
from app.db.models.knowledge_chunk import KnowledgeChunkModel
from app.db.models.conversation_history import ConversationModel
from app.db.models.processed_event import ProcessedEventModel

__all__ = [
    "CourseModel",
    "BranchModel",
    "FeePolicyModel",
    "ProgramFeeModel",
    "EligibilityPolicyModel",
    "ProgramEligibilityModel",
    "AvailabilityInfoModel",
    "AdmissionStatusModel",
    "KnowledgeChunkModel",
    "ConversationModel",
    "ProcessedEventModel",
]
