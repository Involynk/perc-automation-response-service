# Phase 4A — Document Inventory & Classification

This document provides a detailed inventory and content classification of all 18 Markdown source documents located in `MockData/unstructured/`.

---

## Document Inventory Table

| # | File Name | Category Code | Intent Category | Information Type | Structured Overlap | RAG Value |
|---|---|---|---|---|---|---|
| 1 | `course-discovery.md` | C1 | `C1_COURSE_DISCOVERY` | Overview, Catalog Table, Contact | High (`courses`, `branches`) | MEDIUM |
| 2 | `course-details.md` | C2 | `C2_COURSE_DETAILS` | Course Profiles, Descriptions | High (`courses`) | HIGH |
| 3 | `fees-pricing.md` | C3 | `C3_FEES_PRICING` | Policy, Inclusions, Table, Contact | High (`fee_policies`, `program_fees`) | HIGH |
| 4 | `eligibility.md` | C4 | `C4_ELIGIBILITY` | General & Program Eligibility, Boards | High (`eligibility_policies`, `program_eligibility`) | HIGH |
| 5 | `branch-location.md` | C5 | `C5_BRANCH_LOCATION` | Address, Coordinates, Landmarks, Contact | High (`branches`) | MEDIUM |
| 6 | `admission-process.md` | C6 | `C6_ADMISSION_PROCESS` | 5-Step Process, Demo, Diagnostic, Contact | High (`eligibility_policies`, `admission_status`) | HIGH |
| 7 | `required-documents.md` | C7 | `C7_REQUIRED_DOCUMENTS` | Checklists (General, Competitive), Advisory | None (Pure Unstructured) | HIGH |
| 8 | `policies.md` | C8 | `C8_POLICIES` | Academic & Institutional Policies, URLs | Partial (`admission_status`, `eligibility_policies`) | HIGH |
| 9 | `availability-status.md` | C9 | `C9_AVAILABILITY_STATUS` | Status, Batch limits, Hours, 1-on-1 | High (`availability_info`, `admission_status`) | MEDIUM |
| 10 | `comparison.md` | C10 | `C10_COMPARISON` | Differentiators, Table, Reviews, Guidance | None (Pure Unstructured) | HIGH |
| 11 | `multi-intent.md` | C11 | `C11_MULTI_INTENT` | Synthetic Q&A Examples (5 Scenarios) | High (Synthesizes across all tables) | LOW |
| 12 | `follow-up-contextual.md` | C12 | `C12_FOLLOW_UP_CONTEXTUAL` | Multi-Turn Dialogue Examples (3 Scenarios) | High (Synthesizes across tables) | LOW |
| 13 | `ambiguous-incomplete.md` | C13 | `C13_AMBIGUOUS_INCOMPLETE` | Disambiguation Examples (6 Scenarios) | Partial (Examples cite real entities) | LOW |
| 14 | `out-of-scope-escalation.md` | C14 | `C14_OUT_OF_SCOPE_ESCALATION` | Boundaries, Handoff rules, 6 Categories | None (Pure Unstructured Policy) | HIGH |
| 15 | `grievance-human-handoff.md` | C15 | `C15_GRIEVANCE_HUMAN_HANDOFF` | Escalation Triggers, Table, Template | None (Pure Unstructured Policy) | HIGH |
| 16 | `hostel-accommodation.md` | C16 | `C16_HOSTEL_ACCOMMODATION` | Day Center Policy, Local PG Guidance | None (Pure Unstructured) | HIGH |
| 17 | `placement-career-outcomes.md` | C17 | `C17_PLACEMENT_CAREER_OUTCOMES` | Testimonials, Pathways, Trust metrics | None (Pure Unstructured) | HIGH |
| 18 | `language-medium.md` | C18 | `C18_LANGUAGE_MEDIUM` | Instruction medium, Multilingual support | None (Pure Unstructured) | HIGH |

---

## Comprehensive Document Profiles

### 1. `course-discovery.md`
- **Category**: `C1_COURSE_DISCOVERY`
- **Purpose**: Provides a macro overview of PERC's 8 course categories, a high-level summary table of all 14 offerings, discovery guidance, and contact channels.
- **Main Sections**:
  - `# PERC Course Discovery`
  - `## Course Categories Available`
  - `## All Programs at a Glance` (Markdown table: Program, Category, Class/Target, Duration)
  - `## How to Discover the Right Course`
  - `## Contact for Program Guidance`
- **Information Types**: Explanatory text, Category list, Summary table, Process guidance, Contact details.
- **Structured Overlap**: Overlaps with `courses` table (names, categories, target classes, durations) and `branches` table (Begur address, phones, email).
- **RAG Value**: **MEDIUM** (The category explanations and discovery advice are useful in RAG, but catalog queries should prioritize the `courses` structured database).

---

### 2. `course-details.md`
- **Category**: `C2_COURSE_DETAILS`
- **Purpose**: Detailed narrative breakdowns for each of PERC's 14 educational programs, detailing subjects, duration, pedagogical focus, target audience, and full narrative descriptions.
- **Main Sections**:
  - `# PERC Course Details`
  - `## PERC Ignite` through `## One-to-One Tuition` (14 discrete subsections, one for each program)
- **Information Types**: Program profiles, Pedagogical focus narratives, Detailed program descriptions.
- **Structured Overlap**: Direct overlap with `courses` table (`target_class`, `category`, `duration`, `subjects`, `focus`, `description`).
- **RAG Value**: **HIGH** (Provides rich narrative descriptions and contextual explanations for subjective inquiries like "How does PERC teach Class 6 science?").

---

### 3. `fees-pricing.md`
- **Category**: `C3_FEES_PRICING`
- **Purpose**: Articulates PERC's fee transparency philosophy, how to inquire about fees, extensive list of what fee covers (tests, study materials, PTMs, doubt sessions), price positioning, and a 14-program fee table.
- **Main Sections**:
  - `# PERC Fees and Pricing`
  - `## Fee Transparency Policy`
  - `## How to Get Fee Information`
  - `## What Is Included in Fees` (11 bullet items detailing inclusions)
  - `## Price Range`
  - `## Program Fee Summary` (Markdown table listing all 14 programs as "Contact PERC")
- **Information Types**: Institutional policy, Step-by-step inquiry process, Detailed fee inclusions list, Market positioning explanation, Fee summary table.
- **Structured Overlap**: High overlap with `fee_policies` (policy note, contact channels, fee inclusions list, price range) and `program_fees` (program list and fee status).
- **RAG Value**: **HIGH** (Explains the nuance behind fee inclusions and why pricing is not published online).

---

### 4. `eligibility.md`
- **Category**: `C4_ELIGIBILITY`
- **Purpose**: Defines open admission philosophy, diagnostic test placement approach, program-by-program eligibility table, free demo class details, supported curriculum boards (CBSE, ICSE, NIOS, State Board), and contact channels.
- **Main Sections**:
  - `# PERC Eligibility Criteria`
  - `## General Eligibility`
  - `## Program-Wise Eligibility` (Markdown table: Program, Eligible Classes, Notes)
  - `## Demo Class`
  - `## Curriculum Board Compatibility` (CBSE, ICSE, NIOS, State Board)
  - `## Contact to Check Eligibility`
- **Information Types**: Policy statement, Program eligibility matrix, Board compatibility guidance, Contact details.
- **Structured Overlap**: High overlap with `eligibility_policies` (general policy, demo class) and `program_eligibility` (program names, eligible classes, notes).
- **RAG Value**: **HIGH** (Board compatibility section for NIOS/State boards is unique unstructured knowledge).

---

### 5. `branch-location.md`
- **Category**: `C5_BRANCH_LOCATION`
- **Purpose**: Details campus location, full address, landmarks, transit/reachability instructions, office hours, batch slots, geo-coordinates, and digital links.
- **Main Sections**:
  - `# PERC Branch and Location`
  - `## Main Campus` (`### Address`, `### Nearby Landmarks`, `### How to Reach`)
  - `## Contact Details`
  - `## Office Timings`
  - `## Batch Timings`
  - `## Geographic Coordinates`
  - `## Online Presence`
- **Information Types**: Physical location data, Directions/Transit advice, Office/batch timing tables, Coordinates, Contact info.
- **Structured Overlap**: Direct overlap with `branches` table (address, geo coordinates, contact phones/emails, timings, batch slots, landmarks, google maps URL).
- **RAG Value**: **MEDIUM** (Transit/reachability narrative is unstructured; raw address/coordinates are authoritative in DB).

---

### 6. `admission-process.md`
- **Category**: `C6_ADMISSION_PROCESS`
- **Purpose**: Complete guide to the 5-step admission workflow (Free Demo → Campus Visit → Diagnostic Test → Program Selection → Enrollment), rolling admissions policy, and contact table.
- **Main Sections**:
  - `# PERC Admission Process`
  - `## Overview`
  - `## Step-by-Step Admission Process` (`### Step 1: Book a Free Demo`, `### Step 2: Visit the Campus`, `### Step 3: Diagnostic Assessment`, `### Step 4: Choose the Right Program`, `### Step 5: Complete Formalities and Start Learning`)
  - `## Admissions Are Open Year-Round`
  - `## Contact for Admissions`
- **Information Types**: Process workflow, Step-by-step descriptions, Policy statement, Contact table.
- **Structured Overlap**: Overlaps with `eligibility_policies` (`admission_process` JSONB array, demo class) and `admission_status` (rolling admission note, batch sizes, contacts).
- **RAG Value**: **HIGH** (Provides natural step-by-step conversational text for student registration queries).

---

### 7. `required-documents.md`
- **Category**: `C7_REQUIRED_DOCUMENTS`
- **Purpose**: Outlines documents needed for admission enrollment, including general documents (report cards, ID proof, photos, parent contacts) and specific requirements for competitive entrance programs (Class 10 marksheet, board affiliation).
- **Main Sections**:
  - `# Required Documents for PERC Admission`
  - `## Overview`
  - `## Commonly Required Documents` (Markdown table: Document, Purpose)
  - `## For Competitive Exam Programs (JEE / NEET / KCET)`
  - `## How to Confirm the Exact Document List`
- **Information Types**: Checklists, Contextual guidance, Document matrix, Verification contacts.
- **Structured Overlap**: **None**. There is no relational table storing document checklists.
- **RAG Value**: **HIGH** (Essential for answering document verification questions).

---

### 8. `policies.md`
- **Category**: `C8_POLICIES`
- **Purpose**: Central compilation of institutional policies: batch size limit (15-20), testing & assessment cadence, study material distribution, doubt clearing, parent communication/PTMs, rolling admissions, demo class, diagnostic assessment, and policy URLs (refund, privacy, terms).
- **Main Sections**:
  - `# PERC Policies`
  - `## Academic Policies` (`### Batch Size Policy`, `### Testing and Assessment Policy`, `### Study Materials Policy`, `### Doubt-Clearing Policy`, `### Parent Communication Policy`)
  - `## Admission Policies` (`### Rolling Admissions`, `### Demo Class Policy`, `### Diagnostic Assessment`)
  - `## Refund Policy`
  - `## Privacy Policy`
  - `## Terms and Conditions`
  - `## Contact for Policy Queries`
- **Information Types**: Institutional policies, Testing cadence, Digital material rights, Legal/policy links, Contact channels.
- **Structured Overlap**: Partially overlaps with `fee_policies` (inclusions), `eligibility_policies` (demo/diagnostic), and `admission_status` (batch size/rolling admission).
- **RAG Value**: **HIGH** (Authoritative source for academic operations, PTM schedules, testing policies, and policy URLs).

---

### 9. `availability-status.md`
- **Category**: `C9_AVAILABILITY_STATUS`
- **Purpose**: Highlights live status (Admissions: OPEN), batch limits (15-20), timing tables for regular (B1, B2) and weekend batches, 1-on-1 private tuition scheduling flexibility, office hours, and contact channels.
- **Main Sections**:
  - `# PERC Availability and Status`
  - `## Current Admission Status`
  - `## Batch Seat Limits`
  - `## Batch Timing Slots`
  - `## One-to-One Tuition Availability`
  - `## Office and Inquiry Hours`
  - `## How to Check Availability`
  - `## Free Demo Class`
- **Information Types**: Operational status, Batch schedules, Timing tables, Contact channels.
- **Structured Overlap**: High overlap with `availability_info` (timings, batch slots, 1-on-1 tuition, contacts) and `admission_status` (current status, seat limits).
- **RAG Value**: **MEDIUM** (Operational facts are authoritative in PostgreSQL; text is useful for narrative synthesis).

---

### 10. `comparison.md`
- **Category**: `C10_COMPARISON`
- **Purpose**: Outlines PERC's unique value proposition versus large national coaching chains (batch size, attention, personalized plans, PTM frequency, direct faculty access), program coverage parity, student outcomes, and decision guide.
- **Main Sections**:
  - `# PERC vs Other Coaching Institutes — Comparison`
  - `## What Makes PERC Different`
  - `## Key Differentiators` (Comparative table: Feature, PERC, Large Coaching Chains)
  - `## Programs Comparison`
  - `## Student Outcomes (from Website)`
  - `## When to Choose PERC` (Decision checklist)
- **Information Types**: Competitive comparison matrix, Value proposition, Student outcomes/reviews, Decision guidance.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Crucial for competitive evaluation and positioning queries).

---

### 11. `multi-intent.md`
- **Category**: `C11_MULTI_INTENT`
- **Purpose**: Provides 5 multi-intent training examples demonstrating how to answer compound inquiries (e.g. Fees + Eligibility, Location + Timings + Program, Program + Admission Process, Batch Size + Teaching Style + Fees, One-to-One + Subject + Timing).
- **Main Sections**:
  - `# Multi-Intent Query Examples for PERC`
  - `## Example 1: Fees + Eligibility`
  - `## Example 2: Location + Timings + Program`
  - `## Example 3: Program + Admission Process`
  - `## Example 4: Batch Size + Teaching Style + Fees`
  - `## Example 5: One-to-One + Subject + Timing`
- **Information Types**: Synthetic query examples, Resolution schemas, Data mapping guides.
- **Structured Overlap**: High overlap across all 8 tables (examples cite facts from DB).
- **RAG Value**: **LOW** (This document is a design guide/prompt example dataset rather than domain knowledge; indexing it in RAG risks returning mock conversation transcripts to users).

---

### 12. `follow-up-contextual.md`
- **Category**: `C12_FOLLOW_UP_CONTEXTUAL`
- **Purpose**: Contains 3 multi-turn conversation scenarios (NEET Program Follow-up, Admission Process Follow-up, Class 8 Program Follow-up) demonstrating context tracking across turns.
- **Main Sections**:
  - `# Follow-Up and Contextual Queries for PERC`
  - `## Scenario 1: NEET Program Inquiry Follow-Up` (Turns 1-3)
  - `## Scenario 2: Admission Process Follow-Up` (Turns 1-3)
  - `## Scenario 3: Class 8 Program Follow-Up` (Turns 1-3)
- **Information Types**: Synthetic multi-turn dialogues, Context maintenance examples.
- **Structured Overlap**: Synthesizes facts from `courses`, `admission_status`, and `fee_policies`.
- **RAG Value**: **LOW** (Synthetic conversational examples; indexing may lead to hallucinated conversational snippets).

---

### 13. `ambiguous-incomplete.md`
- **Category**: `C13_AMBIGUOUS_INCOMPLETE`
- **Purpose**: Contains 6 examples of vague/incomplete queries (e.g., "What courses do you have?", "Where are you?", "What are the timings?") and recommended clarification responses.
- **Main Sections**:
  - `# Ambiguous and Incomplete Queries for PERC`
  - `## Example 1: Vague Program Query` through `## Example 6: Typo / Misspelled Program Name`
- **Information Types**: Disambiguation examples, Clarification patterns.
- **Structured Overlap**: Partial (cites real entities like address and program names).
- **RAG Value**: **LOW** (Useful for prompt engineering/system guidelines, but should not be directly retrieved as domain facts).

---

### 14. `out-of-scope-escalation.md`
- **Category**: `C14_OUT_OF_SCOPE_ESCALATION`
- **Purpose**: Specifies institute boundaries across 6 categories (Competitor comparisons, Schools/Colleges, Non-academic careers like pilots/NDA, General/local queries, Escalation to human, Medical/exam anxiety emergencies).
- **Main Sections**:
  - `# Out-of-Scope and Escalation Queries for PERC`
  - `## Category 1: Queries About Other Institutes`
  - `## Category 2: Questions About Other Schools / Colleges`
  - `## Category 3: Career Counseling Beyond Academics`
  - `## Category 4: Non-Academic / General Queries`
  - `## Category 5: Escalation to Human`
  - `## Category 6: Medical / Emergency Queries`
- **Information Types**: Policy boundaries, Refusal templates, Compassionate responses, Escalation triggers.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Contains vital guardrail responses for safety, emergency handling, and scope bounding).

---

### 15. `grievance-human-handoff.md`
- **Category**: `C15_GRIEVANCE_HUMAN_HANDOFF`
- **Purpose**: Establishes 8 mandatory human escalation triggers (refund disputes, staff complaints, academic concerns, admission rejections, grievances, legal queries, emergencies, in-person meetings), grievance handling priority matrix, response template, and contacts.
- **Main Sections**:
  - `# PERC Grievance Handling and Human Handoff`
  - `## When to Escalate to Human` (8 numbered triggers)
  - `## Escalation Response Template`
  - `## Grievance Categories and Handling` (Table: Grievance Type, Handler, Priority)
  - `## PERC Contact for Grievances`
  - `## Refund Policy Reference` (URL)
- **Information Types**: Escalation rules, Response templates, Routing matrix, Contact details.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Critical governance document for safety and human handoff).

---

### 16. `hostel-accommodation.md`
- **Category**: `C16_HOSTEL_ACCOMMODATION`
- **Purpose**: Clarifies that PERC is strictly a day coaching institute and does not provide on-campus hostels; provides guidance on nearby private PG options in Begur / Electronic City corridor and contact details.
- **Main Sections**:
  - `# PERC Hostel and Accommodation`
  - `## Does PERC Offer Hostel or Accommodation Facilities?`
  - `## Out-of-Scope Handling` (Standard response template)
  - `## Nearby Area Information`
  - `## Contact PERC for Local Guidance`
- **Information Types**: Explicit facility status, Out-of-scope response template, Local geographic guidance.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Directly answers hostel/boarding inquiries with approved messaging).

---

### 17. `placement-career-outcomes.md`
- **Category**: `C17_PLACEMENT_CAREER_OUTCOMES`
- **Purpose**: Clarifies that PERC is a coaching institute (not a job placement agency), highlights real student testimonials (Meera K. 95% Class 10 CBSE, Ananya Prasad 650 NEET / KMC Manipal), career pathway mapping, social proof (4.9 stars, 124+ reviews, 1000+ mentored), and negative boundaries.
- **Main Sections**:
  - `# PERC Placement and Career Outcomes`
  - `## About PERC and Career Outcomes`
  - `## Known Student Outcomes` (Testimonials table)
  - `## Programs That Lead to Career Paths` (Mapping table)
  - `## Social Proof and Trust Signals`
  - `## What PERC Does Not Offer`
  - `## Contact for More Information`
- **Information Types**: Institutional scope clarification, Testimonials, Career pathway matrix, Social proof metrics, Negative constraints.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Essential for answering questions regarding results, alumni outcomes, and reviews).

---

### 18. `language-medium.md`
- **Category**: `C18_LANGUAGE_MEDIUM`
- **Purpose**: Details English as primary medium of instruction, multilingual support (Hindi, Kannada for doubt clearing and parent communication), support for Kannada-medium students, KCET bilingual context, and contacts.
- **Main Sections**:
  - `# PERC Language and Medium of Instruction`
  - `## Primary Language of Instruction`
  - `## Additional Languages Supported` (Table: Language, Availability)
  - `## Medium of Teaching` (Breakdown: Classroom, Doubt clearing, Study materials, Parent communication)
  - `## For Kannada-Medium Students`
  - `## KCET and Karnataka Board Students`
  - `## Contact for Language Queries`
- **Information Types**: Language policy, Multilingual breakdown table, Vernacular student support guidelines, Contacts.
- **Structured Overlap**: **None**.
- **RAG Value**: **HIGH** (Definitive guide for all language and medium of instruction queries).
