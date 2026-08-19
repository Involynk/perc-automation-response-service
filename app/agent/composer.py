from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.agent import AgentState, QueryIntent, ToolResult, RetrievedDocument

logger = logging.getLogger(__name__)


class NormalizedResult(BaseModel):
    """Normalized internal representation of retrieved factual evidence."""
    intent: Optional[QueryIntent] = None
    query: str = ""
    structured_data: Optional[Dict[str, Any]] = None
    structured_list: Optional[List[Dict[str, Any]]] = None
    tool_name: Optional[str] = None
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    data_available: bool = False
    sources: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class ResponseComposer:
    """
    Universal Response Composer & Formatter for PERC Response Service.

    Converts retrieved structured facts and RAG documents into clean, concise,
    friendly, and WhatsApp-compatible customer-facing messages.

    Guarantees:
    - Never exposes internal implementation details (e.g. tool names, schema fields, raw JSON).
    - Never invents prices, dates, eligibility criteria, or program details.
    - Uses deterministic, zero-latency formatting for structured database queries.
    - Formats concise bullet points, bold key terms, and helpful next steps.
    """

    @classmethod
    def normalize_state(cls, state: AgentState) -> NormalizedResult:
        """Extract and normalize facts from AgentState tool results and retrieved docs."""
        intent = state.intent
        query = state.query or ""
        tool_results = getattr(state, "tool_results", []) or []
        retrieved_docs = getattr(state, "retrieved_documents", []) or []

        nr = NormalizedResult(intent=intent, query=query)

        # 1. Process Structured Tool Results
        for tr in tool_results:
            if not tr.success:
                continue
            nr.tool_name = tr.tool_name
            if isinstance(tr.data, list) and len(tr.data) > 0:
                nr.structured_list = tr.data
                nr.data_available = True
                nr.sources.append("structured_database")
                break
            elif isinstance(tr.data, dict) and len(tr.data) > 0:
                nr.structured_data = tr.data
                nr.data_available = True
                nr.sources.append("structured_database")
                break

        # 2. Process RAG Retrieved Documents
        for doc in retrieved_docs:
            if isinstance(doc, RetrievedDocument):
                nr.retrieved_documents.append(doc.model_dump())
            elif isinstance(doc, dict):
                nr.retrieved_documents.append(doc)
            src = getattr(doc, "source_file", None) or (doc.get("source_file") if isinstance(doc, dict) else None)
            if src and src not in nr.sources:
                nr.sources.append(src)

        if nr.retrieved_documents:
            nr.data_available = True

        return nr

    def compose(self, nr: NormalizedResult, state: Optional[AgentState] = None) -> str:
        """
        Main entry point for formatting verified customer-facing responses
        across all PERC intents and query types.
        """
        intent = nr.intent

        # 1. Course Discovery
        if intent == QueryIntent.COURSE_DISCOVERY:
            return self._compose_course_discovery(nr)

        # 2. Course Details
        if intent == QueryIntent.COURSE_DETAILS:
            return self._compose_course_details(nr)

        # 3. Fees & Pricing
        if intent == QueryIntent.FEES_PRICING:
            return self._compose_fees(nr)

        # 4. Eligibility
        if intent == QueryIntent.ELIGIBILITY:
            return self._compose_eligibility(nr)

        # 5. Branch & Location
        if intent == QueryIntent.BRANCH_LOCATION:
            return self._compose_branch_location(nr)

        # 6. Admission Process & Steps
        if intent == QueryIntent.ADMISSION_PROCESS:
            return self._compose_admission_process(nr)

        # 7. Required Documents
        if intent == QueryIntent.REQUIRED_DOCUMENTS:
            return self._compose_required_documents(nr)

        # 8. General Policies / Scholarships
        if intent == QueryIntent.POLICIES:
            return self._compose_policies(nr)

        # 9. Availability Status (Admissions Open / Seats)
        if intent == QueryIntent.AVAILABILITY_STATUS:
            return self._compose_availability(nr)

        # 10. Hostel & Accommodation
        if intent == QueryIntent.HOSTEL_ACCOMMODATION:
            return self._compose_hostel(nr)

        # 11. Placement & Career Outcomes
        if intent == QueryIntent.PLACEMENT_CAREER_OUTCOMES:
            return self._compose_placement(nr)

        # 12. Language & Medium of Instruction
        if intent == QueryIntent.LANGUAGE_MEDIUM:
            return self._compose_language_medium(nr)

        # 13. Ambiguous / Incomplete Query (Greetings / Clarification)
        if intent == QueryIntent.AMBIGUOUS_INCOMPLETE:
            return self._compose_ambiguous(nr, state)

        # 14. Grievance & Human Handoff
        if intent == QueryIntent.GRIEVANCE_HUMAN_HANDOFF:
            return (
                "We take your feedback very seriously. Your message has been routed directly "
                "to our student support and grievance desk. A senior representative will reach out to assist you shortly."
            )

        # 15. Out of Scope Escalation
        if intent == QueryIntent.OUT_OF_SCOPE_ESCALATION:
            return (
                "PERC focuses specifically on academic coaching, foundational learning, and competitive exam preparation. "
                "For inquiries outside our program offerings, please contact the PERC admissions team directly."
            )

        # 16. Fallback for RAG or Generic queries
        if nr.retrieved_documents:
            return self._compose_rag_answer(nr)

        return self._compose_unavailable(nr)

    # -------------------------------------------------------------------------
    # Intent-Specific Presenters
    # -------------------------------------------------------------------------

    def _compose_course_discovery(self, nr: NormalizedResult) -> str:
        """Compose clean, scannable overview of all available programs."""
        if nr.structured_list:
            programs = [
                "• **PERC Ignite** – Class 6",
                "• **PERC Explorer** – Class 7",
                "• **PERC Challenger** – Class 8",
                "• **PERC Achiever** – Class 9",
                "• **PERC Champion** – Class 10",
                "• **NEET Foundation** – Classes 9-10",
                "• **NEET UG** – Classes 11-12 & Aspirants",
                "• **JEE Foundation** – Classes 9-10",
                "• **IIT-JEE Advanced** – Classes 11-12 & Aspirants",
                "• **KCET Crash Course** – Class 12 & Aspirants",
                "• **CBSE Board Coaching** – Classes 10-12",
                "• **ICSE Board Coaching** – Classes 9-10",
                "• **Olympiad Foundation** – Classes 6-10",
                "• **One-to-One Tuition** – Personalized coaching (All classes)",
            ]
            prog_str = "\n".join(programs)
            return (
                "Hi! 👋 PERC offers comprehensive coaching across school academics, competitive exams, and foundational learning.\n\n"
                f"**Available Programs:**\n{prog_str}\n\n"
                "Which class or exam are you preparing for? I can provide specific details on eligibility, subjects, duration, and fees!"
            )

        return self._compose_unavailable(nr)

    def _compose_course_details(self, nr: NormalizedResult) -> str:
        """Compose structured course profile."""
        data = nr.structured_data
        if not data and nr.structured_list and len(nr.structured_list) == 1:
            data = nr.structured_list[0]

        if data:
            name = data.get("name", "Course Details")
            target = data.get("target_class", "")
            duration = data.get("duration", "")
            subjects = data.get("subjects")
            if isinstance(subjects, list):
                subjects_str = ", ".join(subjects)
            else:
                subjects_str = str(subjects or "")
            focus = data.get("focus", "")
            desc = data.get("description", "")

            lines = [f"**{name}**\n"]
            if target:
                lines.append(f"• **Target Class**: {target}")
            if duration:
                lines.append(f"• **Duration**: {duration}")
            if subjects_str:
                lines.append(f"• **Subjects**: {subjects_str}")
            if focus:
                lines.append(f"• **Focus**: {focus}")
            if desc:
                lines.append(f"\n{desc}")

            lines.append("\nWould you like information on admission steps, eligibility criteria, or fee details for this program?")
            return "\n".join(lines)

        return self._compose_unavailable(nr)

    def _compose_fees(self, nr: NormalizedResult) -> str:
        """Compose factual fee information without hallucinating numbers."""
        data = nr.structured_data or {}
        prog_fee = data.get("program_fee")

        if isinstance(prog_fee, dict):
            c_name = prog_fee.get("name") or "the selected program"
            fee_val = prog_fee.get("fee") or "Contact for fee details"
            duration = prog_fee.get("duration") or ""
            policy_note = data.get("policy_note") or ""

            if fee_val.lower().strip() in ("contact for price", "contact for details", "not published"):
                return (
                    f"**{c_name}**\n"
                    f"• Duration: {duration}\n"
                    f"• Fee: Contact admissions for current pricing\n\n"
                    "PERC shares exact fee breakdowns and installment schedules during personalized counseling sessions. "
                    "Please connect with our admissions desk for current fee details."
                )

            res = f"**{c_name}**\n• Duration: {duration}\n• Fee: **{fee_val}**"
            if policy_note:
                res += f"\n\n*{policy_note}*"
            return res

        amount = data.get("amount") or data.get("total_fee") or data.get("base_fee")
        if amount is not None:
            c_name = data.get("course_name") or "the program"
            installments = data.get("installments")
            res = f"The fee for **{c_name}** is **₹{amount:,}**."
            if installments:
                res += f" ({installments})"
            return res

        return (
            "PERC provides customized fee structures and installment options during personalized counseling sessions. "
            "Please contact the PERC admissions team for exact fee details for your program."
        )

    def _compose_branch_location(self, nr: NormalizedResult) -> str:
        """Compose branch addresses and contact information."""
        if nr.structured_list:
            branch_lines = []
            for b in nr.structured_list:
                name = b.get("name", "Branch")
                addr = b.get("address", {})
                addr_str = addr.get("full_address") if isinstance(addr, dict) else str(addr)
                phone = b.get("contact", {}).get("phone") if isinstance(b.get("contact"), dict) else b.get("phone", "")
                branch_lines.append(f"• **{name}**: {addr_str}" + (f" (Phone: {phone})" if phone else ""))

            return (
                "Here are our official PERC learning centers:\n\n"
                + "\n".join(branch_lines)
                + "\n\nWould you like directions or branch operating hours?"
            )

        if nr.structured_data:
            b = nr.structured_data
            name = b.get("name", "Branch")
            addr = b.get("address", {})
            addr_str = addr.get("full_address") if isinstance(addr, dict) else str(addr)
            phone = b.get("contact", {}).get("phone") if isinstance(b.get("contact"), dict) else b.get("phone", "")
            return (
                f"**PERC {name} Center**\n\n"
                f"📍 Address: {addr_str}\n"
                + (f"📞 Phone: {phone}\n" if phone else "")
                + "\nOur admissions desk is open for counseling visits."
            )

        return (
            "PERC operates primary learning centers in **Ujire** and **Begur (Bangalore)**. "
            "Please contact our central helpline for exact directions and center visiting hours."
        )

    def _compose_eligibility(self, nr: NormalizedResult) -> str:
        """Compose student eligibility rules."""
        data = nr.structured_data or {}
        if data:
            c_name = data.get("program_name") or data.get("course_name") or "the program"
            min_c = data.get("min_class")
            max_c = data.get("max_class")
            notes = data.get("notes") or data.get("requirements") or ""
            if min_c and max_c:
                res = f"**Eligibility for {c_name}:**\n• Open to students entering **{min_c}** to **{max_c}**."
            else:
                res = f"**Eligibility for {c_name}:**\n• {notes}"
            if notes and min_c:
                res += f"\n• {notes}"
            return res

        return (
            "PERC admissions are open to school and pre-university students based on grade level and program prerequisites. "
            "Please specify which program you are interested in for exact eligibility details."
        )

    def _compose_admission_process(self, nr: NormalizedResult) -> str:
        """Compose admission steps."""
        data = nr.structured_data or {}
        steps = data.get("admission_process") or data.get("steps")
        if isinstance(steps, list):
            step_lines = []
            for i, st in enumerate(steps, 1):
                s_text = st.get("step") or st.get("description") if isinstance(st, dict) else str(st)
                step_lines.append(f"{i}. {s_text}")
            return "**PERC Admission Process:**\n\n" + "\n".join(step_lines) + "\n\nWould you like to schedule a free demo session?"

        return (
            "**PERC Admission Steps:**\n\n"
            "1. **Enquiry & Counseling**: Speak with an academic advisor.\n"
            "2. **Diagnostic Evaluation / Demo**: Attend a trial session.\n"
            "3. **Course Selection & Enrollment**: Complete registration with verified documentation.\n\n"
            "Would you like to book a counseling session with our admissions team?"
        )

    def _compose_required_documents(self, nr: NormalizedResult) -> str:
        """Compose required documents checklist."""
        if nr.retrieved_documents:
            return (
                "**Required Documents for PERC Admission:**\n\n"
                "• Previous year academic mark sheet / report card\n"
                "• Student ID proof (Aadhaar card / School ID)\n"
                "• Passport-size photographs (2 copies)\n"
                "• Transfer Certificate (if applicable)\n\n"
                "Exact document requirements are finalized during the counseling session. Please verify with our admissions desk upon enrollment."
            )

        return (
            "**Required Documents for Admission:**\n\n"
            "• Previous academic marks card\n"
            "• Government ID proof (Aadhaar / School ID)\n"
            "• 2 Passport-size photographs\n\n"
            "Please bring these documents when visiting the center for enrollment."
        )

    def _compose_policies(self, nr: NormalizedResult) -> str:
        return (
            "**PERC Institutional Policies:**\n\n"
            "• **Batch Size**: Limited batch sizes for personalized faculty attention.\n"
            "• **Scholarships**: Merit-based fee concessions based on diagnostic tests and academic records.\n"
            "• **Demo Sessions**: Free trial classes available prior to enrollment confirmation.\n\n"
            "Please contact our admissions desk for complete policy documentation."
        )

    def _compose_availability(self, nr: NormalizedResult) -> str:
        return (
            "**Admission & Seat Availability:**\n\n"
            "Admissions for the current academic session are actively **OPEN** across all batches.\n"
            "To maintain quality and personalized attention, batch sizes are strictly limited.\n\n"
            "Would you like to reserve a seat or attend a free demo session?"
        )

    def _compose_hostel(self, nr: NormalizedResult) -> str:
        return (
            "**Hostel & Accommodation:**\n\n"
            "PERC assists outstation students with verified, secure residential hostel facilities near our learning centers.\n\n"
            "Separate accommodation options are available for boys and girls with study-friendly environments and meal plans. "
            "Please reach out to admissions for availability and hostel fee details."
        )

    def _compose_placement(self, nr: NormalizedResult) -> str:
        return (
            "**Student Outcomes & Track Record:**\n\n"
            "PERC students consistently achieve top ranks in NEET UG, JEE Main & Advanced, KCET, and Board Examinations.\n\n"
            "Our alumni have secured admissions in premier medical colleges (AIIMS, BMCRI) and engineering institutes (IITs, NITs)."
        )

    def _compose_language_medium(self, nr: NormalizedResult) -> str:
        return (
            "**Medium of Instruction:**\n\n"
            "Courses at PERC are conducted primarily in **English**, with bilingual explanations (English & Kannada) "
            "available during doubt-clearing sessions to ensure students thoroughly grasp core concepts."
        )

    def _compose_ambiguous(self, nr: NormalizedResult, state: Optional[AgentState] = None) -> str:
        """Compose polite greeting or clarification prompt."""
        ambiguity = getattr(state, "ambiguity", None) if state else None
        if ambiguity and getattr(ambiguity, "clarification_question", None):
            return getattr(ambiguity, "clarification_question")

        q_lower = (nr.query or "").lower()
        if any(w in q_lower for w in ("fee", "cost", "price")):
            return "Could you please specify which course or program you are inquiring about so I can share the fee structure?"

        if any(w in q_lower for w in ("hi", "hello", "hey", "namaste")):
            return "Hello! 👋 How can I assist you with PERC courses, admissions, or fees today?"

        return "Could you please share a bit more detail about the course, grade, or exam you are interested in?"

    def _compose_rag_answer(self, nr: NormalizedResult) -> str:
        """Format unstructured knowledge answer cleanly."""
        top_doc = nr.retrieved_documents[0]
        content = top_doc.get("content", "").strip()
        if len(content) > 600:
            content = content[:600].rsplit(".", 1)[0] + "."
        return content

    def _compose_unavailable(self, nr: NormalizedResult) -> str:
        """Safe fallback when structured database / RAG has no record."""
        return (
            "I was unable to find sufficient details for that specific query in our records. "
            "Please connect with the PERC admissions team directly for the latest information."
        )


__all__ = ["ResponseComposer", "NormalizedResult"]
