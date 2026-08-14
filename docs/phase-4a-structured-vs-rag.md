# Phase 4A — Structured Source of Truth vs. RAG Knowledge

This document establishes the architectural boundary, authority hierarchy, and overlap analysis between the **Structured PostgreSQL Relational Layer** and the **Unstructured RAG Knowledge Base** for the PERC Response Service.

---

## 1. Architectural Boundary Principles

To prevent hallucinations, data discrepancies, and conflicting student responses, the system enforces a strict **Dual-Layer Authority Hierarchy**:

```
+-------------------------------------------------------------------------+
|                  PERC DUAL-LAYER KNOWLEDGE ARCHITECTURE                 |
+-------------------------------------------------------------------------+
|                                                                         |
|  [ LAYER 1: STRUCTURED RELATIONAL DATABASE (POSTGRESQL / SUPABASE) ]    |
|  * Authoritative for deterministic facts, IDs, policies, exact status  |
|  * Entities: Courses, Branches, Fees, Eligibility, Batches, Admission   |
|  * Query Mechanism: SQL via Repository & StructuredDataService         |
|                                                                         |
|  [ LAYER 2: UNSTRUCTURED RAG KNOWLEDGE (VECTOR STORE / MARKDOWN) ]      |
|  * Authoritative for explanations, reasoning, pedagogy, social proof    |
|  * Entities: Teaching methodology, Documents list, Comparisons, Tone    |
|  * Query Mechanism: Vector similarity + Metadata filtered retrieval     |
|                                                                         |
+-------------------------------------------------------------------------+
```

### Core Invariant
> **Rule of Deterministic Authority**: When an inquiry asks for a structured entity attribute (e.g. course duration, branch GPS coordinates, official fee policy contact, live batch seat status, class eligibility bounds), the **Structured Database is the sole source of truth**. A Markdown chunk retrieved via RAG must NEVER override or contradict an active database record.

---

## 2. Comprehensive Overlap & Authority Matrix

The following matrix maps every domain subject area to its authoritative source, secondary supporting source, and resolution rule:

| Subject / Entity Domain | Authoritative Source | Secondary Source | Resolution Rule / Precedence |
|---|---|---|---|
| **Course Catalog & Codes** (ID, Category, Target Class, Subjects, Duration) | `courses` (DB) | `course-details.md`, `course-discovery.md` (RAG) | DB wins strictly. RAG provides narrative explanations of pedagogical focus. |
| **Branch & Campus Logistics** (Address, Phone, Email, Office Hours, Geolocation) | `branches` (DB) | `branch-location.md` (RAG) | DB wins strictly. RAG provides transit/landmarks context ("How to reach via cab/auto"). |
| **Fee Information & Policy** (Fee transparency policy, Contact numbers, Inclusions) | `fee_policies`, `program_fees` (DB) | `fees-pricing.md` (RAG) | DB wins strictly for fee status ("Contact for price"). RAG provides detailed explanation of what is included (printed materials, test series). |
| **Eligibility Rules & Grades** (Min/Max class, Diagnostic test, Demo class) | `eligibility_policies`, `program_eligibility` (DB) | `eligibility.md` (RAG) | DB wins for grade boundaries. RAG provides details on board compatibility (CBSE, ICSE, NIOS, State Board). |
| **Admission Process & Milestones** (5-step process, Counseling, Enrollment) | `eligibility_policies.admission_process` (DB) | `admission-process.md` (RAG) | DB provides the canonical 5-step sequence. RAG provides conversational descriptions of each step. |
| **Live Admission & Seat Status** (Current status: OPEN, Batch size: 15-20) | `admission_status` (DB) | `availability-status.md` (RAG) | DB wins strictly. Live status is dynamic in DB; RAG must not assert fixed admission status if DB says CLOSED. |
| **Batch Timings & Schedules** (B1: 4:30-6:30 PM, B2: 6:30-8:30 PM, Weekend) | `branches.batch_slots`, `availability_info` (DB) | `availability-status.md`, `branch-location.md` (RAG) | DB wins. RAG provides conversational context for flexible 1-on-1 private tuition scheduling. |
| **Required Admission Documents** (ID proof, photos, marks cards) | `required-documents.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Institutional & Academic Policies** (Testing cadence, PTMs, Study materials, URLs) | `policies.md` (RAG) | `fee_policies` (DB partial) | **Pure RAG Knowledge** for testing policy, PTM rules, and external URLs (refund, privacy, terms). |
| **Competitor Comparison & Differentiators** (PERC vs Chains, Batch size comparison) | `comparison.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Human Escalation & Grievance Rules** (8 triggers, Routing matrix, Templates) | `grievance-human-handoff.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Scope Boundaries & Refusals** (Schools, Pilot training, Medical emergencies) | `out-of-scope-escalation.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Hostel & Accommodation Guidance** (Day center policy, Nearby PG search advice) | `hostel-accommodation.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Placement & Career Outcomes** (Alumni testimonials, Trust signals, Ratings) | `placement-career-outcomes.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Language & Medium of Instruction** (English primary, Hindi/Kannada support) | `language-medium.md` (RAG) | None (Not in DB) | **Pure RAG Knowledge**. Authoritative in RAG. |
| **Synthetic Multi-Turn / Multi-Intent Examples** | Mock Data only | None | **Do NOT index for factual retrieval**. Used solely for evaluation and prompting. |

---

## 3. Potential Conflicts & Data Inconsistencies Identified

During the comprehensive analysis of all 18 Markdown files and the PostgreSQL database tables/MockData, the following nuances and potential discrepancies were identified:

### 3.1 Batch Timing Representation
- **Structured DB (`branches.json` / `branches` table)**: Defines batch slots as `B1` (4:30 PM - 6:30 PM) and `B2` (6:30 PM - 8:30 PM).
- **Unstructured Markdown (`availability-status.md`, `branch-location.md`)**: Adds an explicit mention of a **"Weekend Batch (On inquiry - Saturday / Sunday for JEE and NEET batches only)"**.
- **Resolution**: The structured database provides the primary weekday schedule. The agent must rely on RAG to explain that weekend batches for JEE/NEET are available *upon special inquiry*.

### 3.2 Program Duration Formats
- **Structured DB (`courses.json`)**: Formatted as `'1 Year'`, `'2 Years'`, `'6 Months'`, `'Flexible'`.
- **Markdown Text (`course-details.md`)**: Matches the DB, but some narrative paragraphs refer to "2-year comprehensive course" or "intensive 6-month crash course".
- **Resolution**: No semantic conflict, but relational DB is used whenever exact course metadata is injected.

### 3.3 Fee Pricing Transparency
- **Structured DB (`fees.json`, `program_fees`)**: Explicitly stores `fee: "Contact PERC"` for all 14 rows, with `general_info` storing the 11 inclusion points and price tier `"Moderate (Rs Rs)"`.
- **Unstructured Markdown (`fees-pricing.md`)**: Contains identical information plus extensive narrative explaining *why* fees are not published online (tailored batch counseling).
- **Resolution**: Total alignment. The structured tool returns the fee status and contact channels, while RAG supplements the explanation of why counseling is needed.

### 3.4 Admission Process Wording
- **Structured DB (`eligibility.json` / `eligibility_policies.admission_process`)**: 5 discrete objects: `[Step 1: Book a Free Demo, Step 2: Visit the Campus, Step 3: Diagnostic Assessment, Step 4: Choose the Right Program, Step 5: Complete Formalities and Start Learning]`.
- **Unstructured Markdown (`admission-process.md`)**: Identical 5-step structure with matching headings and descriptions.
- **Resolution**: 100% consistent across both layers.

---

## 4. Architectural Rules for Future Agent Integration

1. **Structured-First for Entity Lookups**: If a student query asks "What is the fee for NEET UG?", the agent invokes `get_fee(course_name='NEET UG')` or `get_course_info()`. RAG is not required unless the user asks "Why do you not publish fees online?" or "What does the fee include?".
2. **RAG-First for Explanations & Policies**: If a student query asks "Do you provide hostel facilities?", "Can you teach in Kannada?", "What documents should I bring?", or "How are you different from Allen/Aakash?", RAG is invoked directly since no relational table holds these qualitative concepts.
3. **No Overriding Allowed**: In a multi-intent query combining structured and unstructured parts (e.g. "Where is the campus and what documents do I need to bring?"), the agent retrieves the address from the structured tool and the document list from RAG, ensuring the address strictly matches the database.
