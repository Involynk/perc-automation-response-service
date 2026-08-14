# Phase 4A — RAG & Unstructured Data Analysis & Design Specification

---

## 1. Executive Summary

This specification delivers the complete RAG (Retrieval-Augmented Generation) design and unstructured knowledge analysis for the **PERC Response Service** (`response-service`).

Based on a thorough, line-by-line inspection of all 18 Markdown source documents in `MockData/unstructured/` and their interplay with the live PostgreSQL structured data layer (Phase 2), this document formalizes:
1. The **inventory & taxonomy** of all unstructured source assets.
2. The **strict boundary & authority hierarchy** between PostgreSQL relational tables and RAG chunks.
3. A **semantic, heading-aware Markdown chunking strategy** that prevents table fragmentation and context loss.
4. A robust **metadata schema** linking vector chunks with domain entities without synthetic hallucination.
5. A **hybrid retrieval architecture** combining semantic dense vectors, BM25 keyword matching, and metadata pre-filtering.
6. Rigorous **RAG safety and guardrail rules** defining when RAG must abstain, escalate, or defer to structured tools.
7. The architectural contract for the future `search_knowledge()` tool.
8. A comprehensive risk log of observed data quirks across the 18 files.

---

## 2. Document Inventory Summary

The 18 Markdown documents in `MockData/unstructured/` align with the system's 18-intent taxonomy (`C1` through `C18`):

```
+----------------------------------------------------------------------------------------------------+
|                                 18 UNSTRUCTURED DOCUMENTS TAXONOMY                                 |
+------------------------------------+------------------------------------+--------------------------+
| High Structured Overlap            | Pure Unstructured (High Value)     | Synthetic Q&A / Scenarios|
| (Secondary to Relational DB)       | (Authoritative in RAG)             | (Exclude from Fact Base) |
+------------------------------------+------------------------------------+--------------------------+
| 1. course-discovery.md (C1)        | 7. required-documents.md (C7)      | 11. multi-intent.md (C11)|
| 2. course-details.md (C2)          | 8. policies.md (C8)                | 12. follow-up.md (C12)   |
| 3. fees-pricing.md (C3)            | 10. comparison.md (C10)            | 13. ambiguous.md (C13)   |
| 4. eligibility.md (C4)             | 14. out-of-scope.md (C14)          |                          |
| 5. branch-location.md (C5)         | 15. grievance-handoff.md (C15)     |                          |
| 6. admission-process.md (C6)       | 16. hostel-accommodation.md (C16)  |                          |
| 9. availability-status.md (C9)     | 17. placement-outcomes.md (C17)    |                          |
|                                    | 18. language-medium.md (C18)       |                          |
+------------------------------------+------------------------------------+--------------------------+
```

### Key Observation on Source Documents
- **Documents 1–6, 9**: Contain extensive domain facts that mirror the 8 PostgreSQL tables (`courses`, `branches`, `fee_policies`, `program_fees`, `eligibility_policies`, `program_eligibility`, `availability_info`, `admission_status`). They provide rich descriptive narratives (e.g. course pedagogy, why fees require counseling).
- **Documents 7, 8, 10, 14–18**: Contain pure institutional knowledge not modeled in SQL (e.g., required document checklists, PTM cadences, competitor differentiators, hostel/PG advice, language options, grievance escalation triggers).
- **Documents 11–13**: Synthetic dialogue transcripts designed as few-shot prompt examples and evaluation scenarios. **They should NOT be indexed as factual knowledge** to avoid corrupting retrieval with simulated user queries.

---

## 3. Structured vs. RAG Boundary & Source Priority

### Authority Matrix
```
                             +-----------------------+
                             |   Incoming Query      |
                             +-----------+-----------+
                                         |
                                         v
                     +---------------------------------------+
                     | Is inquiry asking for exact entity,   |
                     | live status, fee, or campus address?  |
                     +-------------------+-------------------+
                                         |
                       YES               |               NO
                        |                |                |
                        v                |                v
         +-----------------------------+ | +-------------------------------+
         | STRUCTURED DATABASE (SQL)   | | | RAG VECTOR RETRIEVAL          |
         | * courses                   | | | * required-documents.md       |
         | * branches                  | | | * policies.md                 |
         | * fee_policies              | | | * comparison.md               |
         | * program_fees              | | | * hostel-accommodation.md     |
         | * eligibility_policies      | | | * language-medium.md          |
         | * program_eligibility       | | | * out-of-scope.md             |
         | * availability_info         | | | * placement-outcomes.md       |
         | * admission_status          | | | * grievance-human-handoff.md  |
         +-----------------------------+ | +-------------------------------+
```

### Precedence Hierarchy
1. **Priority 1 (Absolute Authority)**: PostgreSQL Relational Database. Authoritative for course IDs, prices/fee policy contacts, eligibility grade bounds, campus addresses, office hours, and live admission open/closed flags.
2. **Priority 2 (Policy & Context Authority)**: Curated Unstructured Knowledge (RAG). Authoritative for academic policies, document checklists, differentiators, language support, and escalation guidelines.
3. **Priority 3 (Fallback / Clarification)**: Agent Clarification Prompt or Human Escalation Router.

---

## 4. Chunking Strategy Recommendation

### 4.1 Rejection of Fixed-Character Chunking
Fixed-character / fixed-token sliding windows (e.g., 500 characters with 50 overlap) are **strictly rejected** because they cause catastrophic semantic failures in these specific Markdown documents:
- Splitting Markdown tables mid-row (e.g. `comparison.md`, `placement-career-outcomes.md`, `required-documents.md`).
- Separating a section heading (`### Step 3: Diagnostic Assessment`) from its descriptive bullet points.
- Fragmenting 5-step sequential workflows across arbitrary chunk boundaries.

### 4.2 Recommended: Semantic Hierarchy-Aware Markdown Chunking
Chunking must respect the document tree:
`Document Root (H1) -> Major Section (H2) -> Sub-Feature / Course (H3)`

```
Document: course-details.md
  ├── H1: # PERC Course Details (Document Title / Context)
  ├── Chunk 1 -> H2: ## PERC Ignite (Target, Category, Duration, Subjects, Focus, Description)
  ├── Chunk 2 -> H2: ## PERC Explorer (...)
  └── ...
  └── Chunk 14 -> H2: ## One-to-One Tuition (...)

Document: policies.md
  ├── Chunk 1 -> H2: ## Academic Policies / H3: ### Batch Size Policy
  ├── Chunk 2 -> H2: ## Academic Policies / H3: ### Testing and Assessment Policy
  ├── Chunk 3 -> H2: ## Academic Policies / H3: ### Parent Communication Policy
  └── ...
```

### 4.3 Chunking Rules & Bounds
- **Chunk Boundary**: Markdown Heading 2 (`##`) or Heading 3 (`###`), depending on section granularity.
- **Context Injection / Breadcrumb Prefixing**: Prepend `# Document Title > ## Section Title` to every chunk text before embedding. This ensures chunks like `### Step 1: Book a Free Demo` retain the parent context `PERC Admission Process`.
- **Table Preservation**: Keep all Markdown tables completely intact within a single chunk.
- **Target Size**: 150 to 450 tokens (approx. 600 to 2,000 characters).
- **Chunk Overlap**: 0 tokens between distinct semantic subheadings. Sequential narrative sections (if exceeding 500 tokens) use a 50-token semantic overlap.

---

## 5. Metadata Design

Every indexed chunk in the future vector store must carry the following structured metadata payload:

```json
{
  "document_id": "policies",
  "source_file": "policies.md",
  "category": "C8_POLICIES",
  "section": "Academic Policies",
  "heading": "Testing and Assessment Policy",
  "document_type": "policy",
  "source_priority": "high",
  "course_id": null,
  "branch_id": null,
  "target_class": null,
  "tags": ["testing", "weekly tests", "mock tests", "assessments"]
}
```

### Field Classification

| Metadata Field | Status | Source / Rule | Example |
|---|---|---|---|
| `document_id` | **REQUIRED** | File stem without extension | `"required-documents"` |
| `source_file` | **REQUIRED** | Relative path to source file | `"required-documents.md"` |
| `category` | **REQUIRED** | Category code from taxonomy (`C1`–`C18`) | `"C7_REQUIRED_DOCUMENTS"` |
| `section` | **REQUIRED** | Parent H2 heading text | `"Commonly Required Documents"` |
| `heading` | **REQUIRED** | Immediate H2 or H3 heading text | `"For Competitive Exam Programs"` |
| `document_type` | **REQUIRED** | Enum: `catalog`, `policy`, `process`, `comparison`, `faq`, `escalation` | `"policy"` |
| `source_priority` | **REQUIRED** | Enum: `authoritative_rag`, `secondary_rag`, `prompt_example` | `"authoritative_rag"` |
| `course_id` | **OPTIONAL** | Exact course ID matching PostgreSQL `courses.id`. Only set when chunk explicitly discusses a single course. | `"neet-ug"`, `"perc-ignite"`, `null` |
| `branch_id` | **OPTIONAL** | Exact branch ID matching PostgreSQL `branches.id`. | `"begur-main"`, `null` |
| `target_class` | **OPTIONAL** | Grade level referenced in chunk | `"Class 10"`, `"Classes 11-12"`, `null` |
| `tags` | **DERIVED** | Extracted topical keywords for hybrid filtering | `["refund", "privacy", "demo"]` |

> [!IMPORTANT]
> **Anti-Hallucination Metadata Rule**: Never invent `course_id` or `branch_id` values when the source document discusses global policies (e.g. `policies.md`, `comparison.md`). Set them strictly to `null`.

---

## 6. Retrieval Strategy Recommendation

To achieve maximum recall and precision, the future RAG subsystem must implement **Hybrid Retrieval with Metadata Filtering**:

```
                              Student Query
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
    [ Dense Vector Search ]                        [ Sparse Keyword Search ]
    (Embedding cosine similarity)                  (BM25 / Full-text search)
            |                                               |
            +-----------------------+-----------------------+
                                    |
                                    v
                     [ Reciprocal Rank Fusion (RRF) ]
                                    |
                                    v
                     [ Metadata Pre/Post-Filtering ]
                     (Category, Course ID, Document Type)
                                    |
                                    v
                    [ Threshold Filter (Score >= 0.70) ]
                                    |
                                    v
                    Top-K Filtered Chunks (k=3 to 5)
```

### Retrieval Parameters
- **Top-K**: Default `k = 3`, maximum `k = 5`.
- **Similarity Threshold**: Dense cosine score $\ge 0.70$. Chunks below 0.70 are discarded as irrelevant.
- **Metadata Pre-Filtering**: When intent classification identifies a specific category (e.g. `C7_REQUIRED_DOCUMENTS` or `C16_HOSTEL_ACCOMMODATION`), filter the search space to relevant categories first.
- **Reranking**: Use a lightweight cross-encoder reranker for complex queries (e.g. `comparison.md` vs `policies.md`).

---

## 7. RAG Safety & Guardrail Rules

### Cases Where RAG Must NOT Answer Directly

1. **Exact Fee Quotes**: RAG chunks contain phrases like "Contact PERC". RAG must not synthesize or guess numerical amounts. It must state the fee transparency policy and provide the official contact number (+91 7259941873).
2. **Current Seat Availability Guarantees**: RAG must state that admissions operate on a rolling basis with 15–20 seat batch limits, but must prompt the user to confirm live batch vacancies via official phone/WhatsApp.
3. **Medical or Severe Exam Anxiety Emergencies**: RAG must immediately return compassionate triage guidance and urge connecting with mental health support / parents, as defined in `out-of-scope-escalation.md`.
4. **Fee Disputes, Staff Grievances, & Refund Requests**: RAG must immediately trigger the **Human Handoff Workflow** with the approved escalation template from `grievance-human-handoff.md`.

### Low-Confidence Behavior
When retrieval returns no chunks with similarity $\ge 0.70$:
1. The RAG tool returns `ToolResult(success=True, data=[], metadata={"retrieval_status": "low_confidence"})`.
2. The agent gracefully informs the student that specific details are unavailable and provides the primary PERC inquiry channels (+91 7259941873 / perc.personalised@gmail.com).

---

## 8. Future `search_knowledge()` Tool Contract

This specification designs the exact interface contract for the future RAG retrieval tool (to be implemented in Phase 4B/4C).

### Input Contract (Pydantic Schema Design)
```python
class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language search query")
    category: Optional[str] = Field(None, description="Optional intent category filter (e.g. C7_REQUIRED_DOCUMENTS)")
    course_id: Optional[str] = Field(None, description="Optional filter by exact course ID")
    branch_id: Optional[str] = Field(None, description="Optional filter by exact branch ID")
    document_type: Optional[str] = Field(None, description="Optional filter by document type (policy, process, etc.)")
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum number of chunks to retrieve")
    min_score: float = Field(default=0.70, ge=0.0, le=1.0, description="Minimum relevance threshold")
```

### Output Contract (`ToolResult` Payload)
```python
class KnowledgeChunk(BaseModel):
    chunk_id: str
    source_file: str
    section: str
    heading: str
    content: str
    relevance_score: float
    metadata: Dict[str, Any]

# Returned inside standard ToolResult:
# ToolResult(
#     tool_name="search_knowledge",
#     success=True,
#     data=[KnowledgeChunk(...), KnowledgeChunk(...)],
#     metadata={"query": "...", "chunks_retrieved": 2}
# )
```

---

## 9. Observed Data Quality Risks Across Source Documents

During inspection of the 18 source files, the following real data characteristics and risks were identified:

| Risk ID | Observed Phenomenon | Source Files Affected | Mitigation in RAG Design |
|---|---|---|---|
| **R-1** | **Synthetic Dialogue Leakage**: Simulated user/agent transcripts exist in source data. | `multi-intent.md`, `follow-up-contextual.md`, `ambiguous-incomplete.md` | **Exclude these 3 files from vector indexing**. Reserve them strictly for test fixtures, prompts, and evaluation. |
| **R-2** | **Repeated Contact Blocks**: Every markdown file repeats the identical phone numbers and Begur address at the footer. | All 18 files | Strip repeated footer contact blocks during chunk extraction to avoid vector dilution and redundant candidate chunks. |
| **R-3** | **Batch Size Redundancy**: The "15 to 20 students per batch" fact appears in 8 different files. | `admission-process.md`, `availability-status.md`, `course-details.md`, `policies.md`, `comparison.md`, etc. | Normal behavior for institutional emphasis. Ensure PostgreSQL `admission_status` remains the authoritative source. |
| **R-4** | **Weekend Batch Discrepancy**: Markdown mentions "Weekend Batch (On inquiry - Saturday/Sunday for JEE/NEET)" which is not in `branches.json` main slot definitions. | `availability-status.md`, `branch-location.md` | Index as qualitative RAG policy; agent clarifies that weekend batches are available *upon special inquiry*. |
| **R-5** | **Overlapping Program Lists**: `course-discovery.md` and `course-details.md` both enumerate all 14 programs. | `course-discovery.md`, `course-details.md` | `course-details.md` is chunked per-program (H2); `course-discovery.md` is indexed as an overview catalog chunk. |

---

## 10. Implementation Recommendations for Subsequent Phases

1. **Phase 4B — Vector Storage & Ingestion Pipeline**:
   - Create Markdown parser implementing the semantic H2/H3 chunking rules.
   - Filter out `multi-intent.md`, `follow-up-contextual.md`, and `ambiguous-incomplete.md` from the embedding corpus.
   - Ingest chunks with full metadata into pgvector / vector index.
2. **Phase 4C — `search_knowledge` Tool Implementation**:
   - Implement the `search_knowledge` tool matching the contract in Section 8.
   - Implement unit and integration tests with mocked and live vector embeddings.
3. **Phase 4D — Agent State Graph Integration**:
   - Connect `search_knowledge` and the 7 structured tools to the agent orchestrator node router.
