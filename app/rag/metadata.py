import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from app.rag.chunker import RawChunk


# Canonical course name to course_id mapping matching resp_courses primary keys
KNOWN_COURSE_MAP = {
    "perc ignite": "perc-ignite",
    "perc explorer": "perc-explorer",
    "perc challenger": "perc-challenger",
    "perc achiever": "perc-achiever",
    "perc champion": "perc-champion",
    "neet foundation": "neet-foundation",
    "neet ug": "neet",
    "neet": "neet",
    "jee foundation": "jee-foundation",
    "iit-jee advanced": "jee",
    "iit jee advanced": "jee",
    "jee": "jee",
    "kcet crash course": "kcet-crash-course",
    "cbse board coaching": "cbse-board",
    "cbse board": "cbse-board",
    "icse board coaching": "icse-board",
    "icse board": "icse-board",
    "olympiad foundation": "olympiad-foundation",
    "one-to-one tuition": "one-to-one-tuition",
}

# Document taxonomy metadata mapping
DOCUMENT_CATEGORY_MAP = {
    "course-discovery": ("C1_COURSE_DISCOVERY", "catalog", "secondary_rag"),
    "course-details": ("C2_COURSE_DETAILS", "catalog", "secondary_rag"),
    "fees-pricing": ("C3_FEES_PRICING", "policy", "secondary_rag"),
    "eligibility": ("C4_ELIGIBILITY", "policy", "secondary_rag"),
    "branch-location": ("C5_BRANCH_LOCATION", "logistics", "secondary_rag"),
    "admission-process": ("C6_ADMISSION_PROCESS", "process", "secondary_rag"),
    "required-documents": ("C7_REQUIRED_DOCUMENTS", "checklist", "authoritative_rag"),
    "policies": ("C8_POLICIES", "policy", "authoritative_rag"),
    "availability-status": ("C9_AVAILABILITY_STATUS", "status", "secondary_rag"),
    "comparison": ("C10_COMPARISON", "comparison", "authoritative_rag"),
    "multi-intent": ("C11_MULTI_INTENT", "prompt_example", "prompt_example"),
    "follow-up-contextual": ("C12_FOLLOW_UP_CONTEXTUAL", "prompt_example", "prompt_example"),
    "ambiguous-incomplete": ("C13_AMBIGUOUS_INCOMPLETE", "prompt_example", "prompt_example"),
    "out-of-scope-escalation": ("C14_OUT_OF_SCOPE_ESCALATION", "escalation", "authoritative_rag"),
    "grievance-human-handoff": ("C15_GRIEVANCE_HUMAN_HANDOFF", "escalation", "authoritative_rag"),
    "hostel-accommodation": ("C16_HOSTEL_ACCOMMODATION", "policy", "authoritative_rag"),
    "placement-career-outcomes": ("C17_PLACEMENT_CAREER_OUTCOMES", "outcomes", "authoritative_rag"),
    "language-medium": ("C18_LANGUAGE_MEDIUM", "policy", "authoritative_rag"),
}


@dataclass
class EnrichedChunk:
    """Represents a fully enriched chunk ready for embedding and database upsert."""
    chunk_id: str
    document_id: str
    source_file: str
    category: str
    document_type: str
    section: str
    heading: str
    chunk_index: int
    content: str
    token_count: int
    source_priority: str
    course_id: Optional[str]
    branch_id: Optional[str]
    target_class: Optional[str]
    metadata_payload: Dict[str, Any]


class MetadataEnricher:
    """
    Enriches raw semantic chunks with category classifications,
    source priority ratings, and safe database foreign key linkages.
    """
    def __init__(self, valid_course_ids: Optional[Set[str]] = None, valid_branch_ids: Optional[Set[str]] = None):
        self.valid_course_ids = valid_course_ids or set(KNOWN_COURSE_MAP.values())
        self.valid_branch_ids = valid_branch_ids or {"begur-main"}

    def extract_course_id(self, document_id: str, heading: str, content: str) -> Optional[str]:
        """Maps course_id strictly if the chunk explicitly discusses a specific course."""
        if document_id == "course-details":
            clean_heading = heading.lower().strip()
            if clean_heading in KNOWN_COURSE_MAP:
                course_id = KNOWN_COURSE_MAP[clean_heading]
                if course_id in self.valid_course_ids:
                    return course_id

        return None

    def extract_branch_id(self, document_id: str, heading: str, content: str) -> Optional[str]:
        """Maps branch_id strictly for campus-specific documents."""
        if document_id == "branch-location":
            return "begur-main"
        return None

    def extract_target_class(self, content: str) -> Optional[str]:
        """Extracts target class mentions if found in structured metadata pattern."""
        match = re.search(r"Target(?:\s*:\s*|\s+)(\bClasses?\s+[0-9]+(?:-[0-9]+)?\b)", content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def enrich_chunk(self, raw_chunk: RawChunk) -> EnrichedChunk:
        doc_id = raw_chunk.document_id
        category, doc_type, priority = DOCUMENT_CATEGORY_MAP.get(
            doc_id, ("C8_POLICIES", "policy", "authoritative_rag")
        )

        course_id = self.extract_course_id(doc_id, raw_chunk.heading, raw_chunk.content)
        branch_id = self.extract_branch_id(doc_id, raw_chunk.heading, raw_chunk.content)
        target_class = self.extract_target_class(raw_chunk.content)

        metadata_payload = {
            "document_id": doc_id,
            "source_file": raw_chunk.source_file,
            "category": category,
            "section": raw_chunk.section,
            "heading": raw_chunk.heading,
            "document_type": doc_type,
            "source_priority": priority,
            "course_id": course_id,
            "branch_id": branch_id,
            "target_class": target_class,
        }

        return EnrichedChunk(
            chunk_id=raw_chunk.chunk_id,
            document_id=doc_id,
            source_file=raw_chunk.source_file,
            category=category,
            document_type=doc_type,
            section=raw_chunk.section,
            heading=raw_chunk.heading,
            chunk_index=raw_chunk.chunk_index,
            content=raw_chunk.content,
            token_count=raw_chunk.token_count,
            source_priority=priority,
            course_id=course_id,
            branch_id=branch_id,
            target_class=target_class,
            metadata_payload=metadata_payload,
        )
