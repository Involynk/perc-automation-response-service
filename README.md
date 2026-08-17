# PERC Response Service

> **Deterministic, Fact-Grounded, Hybrid AI Response Service for Educational Inquiries**

The **PERC Response Service** is a high-reliability AI query-answering engine engineered specifically for the PERC educational institute. It processes parent and student inquiries across admissions, courses, fees, branches, eligibility, and institutional policies.

The service uses a **multi-stage LangGraph pipeline** running behind a **FastAPI** web interface. It combines **deterministic PostgreSQL database tools** with **hybrid semantic RAG retrieval**, enforces strict fact-protection guardrails against hallucinated fee and seat figures, and synthesizes answers via local **Ollama (Qwen3:8B)** or deterministic test providers.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Complete Request Flow](#3-complete-request-flow)
4. [Query Understanding (C1–C18)](#4-query-understanding-c1c18)
5. [Routing Matrix](#5-routing-matrix)
6. [Structured Data Layer](#6-structured-data-layer)
7. [RAG Knowledge Layer](#7-rag-knowledge-layer)
8. [Safety & Fact Protection Guardrails](#8-safety--fact-protection-guardrails)
9. [Answer Generation](#9-answer-generation)
10. [Draft Validation](#10-draft-validation)
11. [FastAPI API Specifications](#11-fastapi-api-specifications)
12. [Configuration](#12-configuration)
13. [Ollama + Qwen3 Setup](#13-ollama--qwen3-setup)
14. [Project Structure](#14-project-structure)
15. [Testing & Verification](#15-testing--verification)
16. [Running Locally](#16-running-locally)
17. [Development Phases Timeline](#17-development-phases-timeline)
18. [Current Status](#18-current-status)
19. [Production Readiness & Remaining Work](#19-production-readiness--remaining-work)
20. [Quick Start](#20-quick-start)

---

## 1. Project Overview

### What the Service Does
The PERC Response Service sits at the core of the PERC automation suite. When prospective students or parents submit inquiries via web or chat interfaces, this service:
1. **Understands & Classifies**: Detects the user's primary intent, secondary intents, and relevant educational entities (classes, exams, courses, branches).
2. **Identifies Ambiguity**: Clarifies incomplete queries before attempting retrieval.
3. **Routes Strategically**: Chooses between deterministic relational database lookup, hybrid RAG knowledge search, multi-intent decomposition, human escalation, or safe stops.
4. **Executes Securely**: Invokes read-only structured tools against PostgreSQL / Supabase or retrieves authoritative markdown chunks.
5. **Verifies Evidence**: Evaluates whether retrieved data is sufficient and conflict-free prior to LLM invocation.
6. **Generates Grounded Answers**: Constructs structured prompts for Ollama Qwen3:8B (or deterministic providers) using strict evidence gating.
7. **Validates Drafts Deterministically**: Scans generated drafts for ungrounded numbers, unsupported claims, or missing disclaimers.
8. **Delivers Standard Responses**: Returns clean, user-facing `ResponseResponse` contracts with explicit sources and status tags.

---

## 2. Architecture

```text
               +----------------------------------+
               |        Client Application        |
               +----------------------------------+
                                 |
                                 | HTTP POST /api/v1/response
                                 v
               +----------------------------------+
               |        FastAPI Web Server        |
               |      (Dependency Injection)      |
               +----------------------------------+
                                 |
                                 | get_response_graph()
                                 v
               +----------------------------------+
               |       Compiled LangGraph         |
               |          (StateGraph)            |
               +----------------------------------+
                                 |
                     +-----------v-----------+
                     |    1. initialize      |
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |    2. understand      | <--- MockDataProvider / Ollama Qwen3
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |    3. ambiguity       |
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |    4. routing         |
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |    5. execution       |
                     +-----+-----------+-----+
                           |           |
           +---------------+           +---------------+
           |                                           |
           v                                           v
+-----------------------+                   +----------------------+
|   Structured Tools    |                   |      Hybrid RAG      |
|  - get_course_info    |                   |  - Vector Search     |
|  - get_fee            |                   |  - BM25 Keyword      |
|  - get_branch_info    |                   |  - RRF Fusion Ranker |
|  - get_eligibility    |                   +----------------------+
|  - get_availability   |                              |
|  - get_admission_*    |                              v
+-----------+-----------+                   +----------------------+
            |                               |  PERC Knowledge Base |
            v                               |  (18 Markdown Docs)  |
+-----------------------+                   +----------------------+
| StructuredDataService |
+-----------+-----------+
            |
            v
+-----------------------+
|  PostgreSQL/Supabase  |
|  (6 Core Relational   |
|   Tables)             |
+-----------------------+
           |                                           |
           +---------------+           +---------------+
                           |           |
                     +-----v-----------v-----+
                     |    6. result_check    | (Deterministic Evidence Gate)
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     |    7. generation      | <--- Ollama Qwen3:8B / Generator
                     +-----------+-----------+
                                 |
                     +-----------v-----------+
                     | 8. result_validation  | (Deterministic Safety Filter)
                     +-----------+-----------+
                                 |
                                 v
               +----------------------------------+
               |     ResponseResponse Schema      |
               |  (session_id, answer, status,    |
               |   sources, intent, clarification)|
               +----------------------------------+
```

### Role of Ollama / Qwen3:8B
- **Query Understanding (Production Mode)**: When `QUERY_UNDERSTANDING_PROVIDER=llm`, Qwen3:8B analyzes complex student queries and outputs JSON containing intent, entities, and ambiguity indicators.
- **Answer Generation**: In `AnswerGenerator`, Qwen3:8B receives locked evidence (extracted structured facts and RAG snippets) and formats the final student response while adhering to strict factual bounds.
- **Testing Isolation**: In test and CI environments, dependency injection isolates Ollama so 100% of pipeline invariants execute without requiring a GPU or active Ollama daemon.

---

## 3. Complete Request Flow

When a client sends `POST /api/v1/response` with `{"session_id": "...", "message": "..."}`, execution proceeds through 8 sequential LangGraph nodes:

```text
POST /api/v1/response
   │
   ├─► 1. initialize_node
   │      - Validates session_id and query message.
   │      - Initializes clean AgentState and merges incoming conversation metadata.
   │
   ├─► 2. understand_node
   │      - Invokes query understanding provider (MockDataProvider or Ollama LLM client).
   │      - Populates state.intent (QueryIntent), state.secondary_intents, state.entities, state.ambiguity.
   │
   ├─► 3. ambiguity_node
   │      - Checks if state.ambiguity.is_ambiguous is True.
   │      - Populates clarification_required=True and context-specific clarification_question.
   │
   ├─► 4. routing_node
   │      - Runs deterministic decide_routing logic across C1–C18 categories.
   │      - Chooses route: STRUCTURED_TOOL, RAG, MULTI_INTENT, CLARIFICATION, HUMAN_HANDOFF, or SAFE_STOP.
   │
   ├─► 5. execution_node
   │      - Executes chosen path via ExecutionEngine.
   │      - Invokes Structured Tools against StructuredDataService or queries hybrid RAG retriever.
   │      - Records ToolResult objects and RetrievedDocument records on the state.
   │
   ├─► 6. result_check_node
   │      - Evaluates evidence sufficiency, detects conflicts, and checks tool success.
   │      - Flags whether generation should proceed, require clarification, or trigger human handoff.
   │
   ├─► 7. generation_node
   │      - If evidence is sufficient: compiles prompt with locked evidence and invokes AnswerGenerator.
   │      - If evidence is insufficient/ambiguous: skips LLM generation and flags reason in metadata.
   │
   ├─► 8. result_validation_node
   │      - Runs deterministic validation on draft answer (hallucination checks, groundedness, price bounds).
   │      - Marks validation_status="validated" or escalates if guardrails fail.
   │
   └─► API Response Mapping
          - Formats AgentState into standard ResponseResponse contract.
          - Returns JSON to client with HTTP 200.
```

---

## 4. Query Understanding (C1–C18)

The system classifies inquiries into 18 canonical intent categories defined in PERC dataset research:

| Code | Intent Category | Example Student Query |
|---|---|---|
| **C1** | `C1_COURSE_DISCOVERY` | *"What courses do you offer at PERC?"* |
| **C2** | `C2_COURSE_DETAILS` | *"Tell me about the 2-Year JEE Advanced program."* |
| **C3** | `C3_FEES_PRICING` | *"How can I find the fee structure for NEET UG?"* |
| **C4** | `C4_ELIGIBILITY` | *"Who can join the NEET Foundation program?"* |
| **C5** | `C5_BRANCH_LOCATION` | *"Where is the PERC center located?"* |
| **C6** | `C6_ADMISSION_PROCESS` | *"How do I enroll at PERC?"* |
| **C7** | `C7_REQUIRED_DOCUMENTS` | *"What documents are needed for admission?"* |
| **C8** | `C8_POLICIES` | *"What is your batch size and refund policy?"* |
| **C9** | `C9_AVAILABILITY_STATUS` | *"Are admissions currently open for Class 11?"* |
| **C10** | `C10_COMPARISON` | *"How is PERC different from large national chains?"* |
| **C11** | `C11_MULTI_INTENT` | *"What is the fee for JEE and what documents are required?"* |
| **C12** | `C12_FOLLOW_UP_CONTEXTUAL` | *"What time are the classes for that batch?"* |
| **C13** | `C13_AMBIGUOUS_INCOMPLETE` | *"What is the fee?"* (missing program/grade) |
| **C14** | `C14_OUT_OF_SCOPE_ESCALATION` | *"Which coaching is better, PERC or BYJU'S?"* |
| **C15** | `C15_GRIEVANCE_HUMAN_HANDOFF` | *"I want to lodge a complaint about my teacher."* |
| **C16** | `C16_HOSTEL_ACCOMMODATION` | *"Do you have hostel facilities for outstation students?"* |
| **C17** | `C17_PLACEMENT_CAREER_OUTCOMES` | *"What are your historical student JEE ranks?"* |
| **C18** | `C18_LANGUAGE_MEDIUM` | *"Is instruction in English or bilingual?"* |

### Providers & Dependency Injection
- **`MockDataProvider`**: Deterministic rule- and mock-based provider used during unit/integration tests and CI.
- **`LLMQueryProvider`**: Production provider that formats user input + context into JSON extraction prompts for Qwen3:8B.
- **`get_query_understanding_provider()`**: Factory function in `app/agent/providers/factory.py` selecting the active provider based on `settings.QUERY_UNDERSTANDING_PROVIDER`.

---

## 5. Routing Matrix

The deterministic router (`app/agent/router.py`) enforces strict priority rules:

```text
Priority: Human Handoff > Ambiguity / Clarification > Safe Stop > Multi-Intent > Structured Tools > RAG
```

| Category | Primary Route | Selected Tool / Action | Rationale |
|---|---|---|---|
| **C1** (Course Discovery) | `STRUCTURED_TOOL` | `get_course_info` | Authoritative course catalog in PostgreSQL |
| **C2** (Course Details) | `STRUCTURED_TOOL` | `get_course_info` | Relational table holds official course specs |
| **C3** (Fees & Pricing) | `STRUCTURED_TOOL` | `get_fee` | Locked fee tables; prevents fee hallucination |
| **C4** (Eligibility) | `STRUCTURED_TOOL` | `get_eligibility` | Min/max grade eligibility rules in DB |
| **C5** (Branch Location) | `STRUCTURED_TOOL` | `get_branch_info` | Verified center addresses and phone numbers |
| **C6** (Admission Process) | `STRUCTURED_TOOL` | `get_admission_steps` | Standardized institutional onboarding steps |
| **C7** (Required Documents) | `RAG` | Hybrid Retrieval (`required-documents.md`) | Document lists and verification guidelines |
| **C8** (Policies) | `RAG` | Hybrid Retrieval (`policies.md`) | Batch size, transfer, and refund clauses |
| **C9** (Availability) | `STRUCTURED_TOOL` | `get_availability` / `get_admission_status` | Relational admission status & batch seat status |
| **C10** (Comparison) | `RAG` | Hybrid Retrieval (`comparison.md`) | Pedagogical differentiation & methodology |
| **C11** (Multi-Intent) | `MULTI_INTENT` | Decomposed Sub-routes | Parallel/sequential execution across intents |
| **C12** (Follow-Up) | `CONTEXTUAL` / `CLARIFICATION` | Sub-intent resolution or Clarification | Resolves previous turn context |
| **C13** (Ambiguous) | `CLARIFICATION` | No Tool Execution | Asks targeted question to resolve missing entities |
| **C14** (Out-of-Scope) | `SAFE_STOP` | No Tool Execution | Escalates out-of-scope/competitor queries safely |
| **C15** (Grievance) | `HUMAN_HANDOFF` | No Tool Execution | Direct handoff to counseling management |
| **C16** (Hostel) | `RAG` | Hybrid Retrieval (`hostel-accommodation.md`) | Accommodation guidance & partner references |
| **C17** (Outcomes) | `RAG` | Hybrid Retrieval (`placement-career-outcomes.md`) | Historical ranks and educational disclaimers |
| **C18** (Language) | `RAG` | Hybrid Retrieval (`language-medium.md`) | Medium of instruction details |

---

## 6. Structured Data Layer

### PostgreSQL Relational Tables (Phase 2)
1. **`courses`**: Course ID, name, duration, target class, target exam, batch size, subjects, status.
2. **`branches`**: Branch ID, name, address, city, phone, email, operating hours.
3. **`fees`**: Program ID, registration fee, tuition fee, installment plans, refund policy notes.
4. **`eligibility`**: Program name, minimum class, maximum class, prerequisites, academic criteria.
5. **`availability`**: Program ID, batch name, total seats, filled seats, waitlist status.
6. **`admission_status`**: Global admission status, academic year, active batch start dates.

### Structured Tools (Phase 3)
Located in `app/tools/structured/`:
- `get_course_info(course_id, name, target_class, exam)`
- `get_fee(course_id, course_name)`
- `get_branch_info(branch_id, name, city)`
- `get_eligibility(program_name, course_id, target_class)`
- `get_admission_steps(program_name)`
- `get_admission_status()`
- `get_availability(program_id, batch_name)`

> [!IMPORTANT]
> **Strict Architectural Rule**: Structured tools ONLY call `StructuredDataService`. They **never** execute raw SQL, never invoke LLM prompts, and never perform free-form natural language generation.

---

## 7. RAG Knowledge Layer

### Document Inventory & Ingestion (Phase 4)
- **18 Knowledge Documents** in `MockData/unstructured/` covering institutional policies, pedagogy, comparisons, language medium, and FAQs.
- **Chunking Strategy**: Hierarchical Markdown header chunking (`H1` -> `H2` -> `H3`) that preserves tables and bulleted lists intact with deterministic IDs (`doc_name#chunk_index`).
- **Hybrid Retrieval**:
  - **Vector Semantic Search**: Cosine similarity against 384-dimensional embeddings (or pgvector in production).
  - **Keyword BM25 Search**: Exact keyword match over terms and course aliases.
  - **Reciprocal Rank Fusion (RRF)**: Merges vector and keyword scores ($RRF\_Score = \sum \frac{1}{60 + rank}$) for optimal precision.

### Authority Hierarchy
```text
PostgreSQL Relational Data (Tier 1 Authority) > Unstructured Markdown RAG (Tier 2 Authority)
```
When facts overlap (e.g. course duration or branch location), structured database results strictly supersede RAG text snippets.

---

## 8. Safety & Fact Protection Guardrails

To protect institutional integrity and prevent hallucinations, the service enforces non-negotiable safety guardrails:

1. **Fee Hallucination Protection**: Fee numbers are only ever output if returned by `get_fee`. The validator blocks any response containing ungrounded currency amounts.
2. **Live Seat Availability Protection**: Seat counts and batch availability are verified exclusively against `get_availability` or `get_admission_status`.
3. **Clarification Gating**: Ambiguous queries (e.g., *"How much does it cost?"* without specifying grade/course) trigger clarification immediately without invoking database queries or LLM generation.
4. **Human Escalation**: Complaints, grievances, or legal/competitor inquiries automatically transition to `status="escalated"` with a counseling handoff notice.
5. **No Blind Hallucination Fallback**: If retrieved evidence is empty or below relevance threshold, answer generation is bypassed and the user is directed to the admissions desk.

---

## 9. Answer Generation

Answer generation (`app/agent/generator.py` and `app/agent/nodes/generation.py`) converts verified evidence into clear student-facing text:

- **Evidence Gate**: Executes only after `result_check_node` verifies evidence is sufficient, non-empty, and free of contradictions.
- **Evidence Serialization**: Structured tool results and RAG text snippets are formatted into a constrained JSON payload.
- **Prompt Structure**: Instructs the LLM to write directly to the student, reference only provided evidence, and refrain from assuming unstated policies.
- **Output Schema**: Produces a strict `DraftAnswerModel` JSON payload:
  ```json
  {
    "draft_answer": "PERC offers classroom coaching...",
    "used_structured": true,
    "used_rag": false,
    "evidence": [...],
    "confidence": 0.95
  }
  ```

---

## 10. Draft Validation

The Phase 5G validation node (`app/agent/result_validator.py` and `app/agent/nodes/result_validation.py`) runs deterministic post-generation checks before any text reaches the student:

- **Groundedness Verification**: Confirms all numeric figures (fees, batch sizes, durations) appear in the source evidence.
- **Safety Scan**: Detects unsupported competitor comparisons or unverified claims.
- **Status Tagging**: Marks valid responses as `status="success"`, or triggers escalation if discrepancies are detected.

---

## 11. FastAPI API Specifications

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness & readiness probe |
| `POST` | `/api/v1/response` | Primary response generation endpoint |
| `POST` | `/response` | Direct root-mounted response endpoint |

### Example Request (`ResponseRequest`)
```json
POST /api/v1/response
Content-Type: application/json

{
  "session_id": "sess-student-8921",
  "message": "What is the fee for the Class 11 IIT-JEE Advanced program?",
  "metadata": {}
}
```

### Example Response (`ResponseResponse`)
```json
HTTP/200 OK
Content-Type: application/json

{
  "session_id": "sess-student-8921",
  "answer": "Fee details for the IIT-JEE Advanced classroom coaching program are provided during your free counseling and demo session.",
  "status": "success",
  "intent": "C3_FEES_PRICING",
  "sources": [
    "structured_database",
    "fees.json"
  ],
  "clarification_required": false,
  "clarification_question": null
}
```

### Example Clarification Response
```json
{
  "session_id": "sess-student-9902",
  "answer": "Could you please specify which course or program you are inquiring about?",
  "status": "clarification_required",
  "intent": "C13_AMBIGUOUS_INCOMPLETE",
  "sources": [],
  "clarification_required": true,
  "clarification_question": "Could you please specify which course or program you are inquiring about?"
}
```

---

## 12. Configuration

Application configuration is managed via Pydantic BaseSettings in `app/core/config.py` using `.env`:

```ini
# Environment
ENVIRONMENT=development

# Database Connection (PostgreSQL / Supabase)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/perc_response_db

# Query Understanding Provider: 'mock' (default for deterministic tests) or 'llm' (production)
QUERY_UNDERSTANDING_PROVIDER=mock

# LLM Provider Configuration
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_TEMPERATURE=0.0

# Ollama Local Service Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT=120
```

---

## 13. Ollama + Qwen3 Setup

To run local answer synthesis with Ollama and Qwen3:

### 1. Install & Start Ollama
- **Windows (PowerShell)**:
  ```powershell
  winget install Ollama.Ollama
  # Or download from https://ollama.com/download/windows
  ```
- **Start Ollama Service**:
  ```bash
  ollama serve
  ```

### 2. Pull Qwen3 Model
```bash
ollama pull qwen3:8b
```

### 3. Verify Local Connectivity
Run the built-in diagnostic smoke test:
```bash
python -m scripts.test_ollama_connection
```

> [!NOTE]
> **Verification Status**: In CI and unit testing, dependency injection mocks the LLM client, allowing all tests to pass without an active Ollama instance. Live Ollama verification occurs dynamically when the service is running.

---

## 14. Project Structure

```text
d:\response-service\
├── alembic/                      # Database migrations
│   └── versions/                 # Initial migration scripts for 6 relational tables
├── app/
│   ├── agent/                    # LangGraph multi-node engine
│   │   ├── nodes/                # 8 discrete pipeline node implementations
│   │   │   ├── initialize.py     # State initialization
│   │   │   ├── understand.py     # Intent & entity classification
│   │   │   ├── ambiguity.py      # Clarification detection
│   │   │   ├── routing.py        # Deterministic routing
│   │   │   ├── execution.py      # Tools/RAG executor
│   │   │   ├── result_check.py   # Evidence evaluation
│   │   │   ├── generation.py     # Answer generation node
│   │   │   └── result_validation.py # Fact validation node
│   │   ├── prompts/              # System prompts for Qwen3
│   │   ├── providers/            # Mock & LLM understanding providers, Ollama client
│   │   ├── executor.py           # Tool execution engine
│   │   ├── generator.py          # Answer generator
│   │   ├── graph.py              # Compiled LangGraph definition
│   │   ├── result_checker.py     # Result sufficiency checker
│   │   ├── result_validator.py   # Draft fact validator
│   │   └── router.py             # C1–C18 routing logic
│   ├── api/                      # FastAPI layer
│   │   ├── deps.py               # Dependency injection (get_response_graph)
│   │   └── v1/
│   │       ├── endpoints/        # POST /response endpoint
│   │       └── router.py         # v1 router assembly
│   ├── core/
│   │   └── config.py             # Pydantic environment settings
│   ├── db/
│   │   ├── models/               # SQLAlchemy models (courses, fees, branches, etc.)
│   │   ├── base.py               # DeclarativeBase
│   │   └── session.py            # Sessionmaker & DB engine
│   ├── rag/                      # Hybrid RAG pipeline
│   │   ├── chunker.py            # Hierarchical markdown chunking
│   │   ├── loader.py             # Document loader
│   │   ├── metadata.py           # Document metadata extractor
│   │   ├── retriever.py          # Vector/keyword retriever
│   │   └── vector_store.py       # Embedding indexer
│   ├── repositories/             # Relational DB repositories
│   ├── schemas/                  # Pydantic schemas (Request, Response, AgentState)
│   ├── services/                 # StructuredDataService
│   ├── tools/                    # Read-only structured tools
│   └── main.py                   # FastAPI application entrypoint
├── docs/                         # Architecture documentation for Phases 1 to 5
├── MockData/                     # Authoritative institutional mock data
│   ├── structured/               # JSON datasets (courses, fees, branches, etc.)
│   └── unstructured/             # 18 Markdown knowledge base documents
├── scripts/                      # Utility scripts
│   ├── check_table_counts.py     # Verify DB row counts
│   ├── ingest_knowledge.py       # RAG knowledge base ingestion
│   ├── seed_structured_data.py   # Seed PostgreSQL tables from MockData
│   └── test_ollama_connection.py # Smoke test for local Ollama daemon
├── tests/                        # Pytest verification suite
│   ├── agent/                    # LangGraph nodes, routing, understanding & E2E tests
│   ├── rag/                      # RAG chunker, loader, and retriever tests
│   ├── tools/                    # Structured tool tests
│   ├── test_api_integration.py   # FastAPI endpoint tests
│   ├── test_config.py            # Configuration tests
│   ├── test_mock_data_parsing.py # Mock data validation
│   ├── test_repositories_and_seeding.py # DB repo tests
│   └── test_schemas.py           # Contract schema tests
├── alembic.ini                   # Alembic configuration
├── pytest.ini                    # Pytest configuration & markers
└── requirements.txt              # Project dependencies
```

---

## 15. Testing & Verification

The repository includes a comprehensive automated test suite with **100% deterministic coverage**:

```bash
pytest -q
```

### Test Suite Summary
- **164 Passed Tests**
- **1 Skipped Test** (Live Ollama smoke test skipped when daemon is offline)
- **0 Failures**
- **0 Deprecation Warnings**
- **Coverage Areas**:
  - Phase 1 API schemas & contracts
  - Phase 2 PostgreSQL models & database seeding
  - Phase 3 Structured read-only tools
  - Phase 4 Hybrid RAG chunking, indexing & RRF retrieval
  - Phase 5 LangGraph nodes (understand, ambiguity, routing, execution, result_check, generation, validation)
  - Phase 5H Real E2E verification across all 18 PERC intent categories
  - FastAPI API integration & exception handling

---

## 16. Running Locally

### 1. Virtual Environment & Dependencies
```bash
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment
```bash
copy .env.example .env
```

### 3. Run Database Migrations & Seed Data
```bash
# Run Alembic migrations
alembic upgrade head

# Seed PostgreSQL with structured institutional data
python -m scripts.seed_structured_data
```

### 4. Ingest RAG Knowledge Base
```bash
python -m scripts.ingest_knowledge
```

### 5. Run Test Suite
```bash
# Run full automated test suite
pytest -q

# Run API integration tests
pytest tests/test_api_integration.py -v

# Run Real E2E verification tests
pytest tests/agent/test_real_e2e.py -v
```

### 6. Start FastAPI Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 7. Test Health & Response Endpoints
```bash
# Health probe
curl http://localhost:8000/health

# Submit query
curl -X POST http://localhost:8000/api/v1/response \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "message": "What courses do you offer?"}'
```

---

## 17. Development Phases Timeline

| Phase | Milestone | Implemented Capabilities |
|---|---|---|
| **Phase 1** | Response Contracts | Defined `ResponseRequest`, `ResponseResponse`, and `AgentState` schemas. |
| **Phase 2** | Structured Data Model | Designed SQLAlchemy models & Alembic migrations for 6 relational tables. |
| **Phase 3** | Structured Tools | Built 7 read-only structured tools calling `StructuredDataService`. |
| **Phase 4A** | RAG Analysis | Cataloged 18 unstructured documents and established authority rules. |
| **Phase 4B** | RAG Ingestion & Vector Storage | Implemented hierarchical chunking and vector storage. |
| **Phase 4C** | Search & Hybrid Retrieval | Built BM25, vector search, and Reciprocal Rank Fusion (RRF). |
| **Phase 5A** | LangGraph Agent Foundation | Built compiled `StateGraph` orchestrating the 8 pipeline nodes. |
| **Phase 5B** | Query Understanding | Integrated C1–C18 intent classification and entity extraction. |
| **Phase 5C** | Deterministic Routing | Built routing matrix across structured tools, RAG, and human handoff. |
| **Phase 5D** | Tool & RAG Execution | Built `ExecutionEngine` managing parallel tool/retrieval execution. |
| **Phase 5E** | Result Checking | Implemented deterministic evidence gatekeeper and conflict detector. |
| **Phase 5F** | Answer Generation | Built `AnswerGenerator` with locked prompt evidence schemas. |
| **Phase 5G** | Draft Validation | Built deterministic fact validator preventing ungrounded claims. |
| **Phase 5H** | Real E2E & API Integration | Wired FastAPI to LangGraph and verified all 18 canonical PERC categories. |

---

## 18. Current Status

### Implemented
- [x] Full FastAPI application entrypoint with `/health`, `/response`, and `/api/v1/response`.
- [x] Complete 8-node compiled LangGraph agent pipeline.
- [x] 6 PostgreSQL relational database models & Alembic migration scripts.
- [x] 7 deterministic read-only structured database tools.
- [x] Hybrid RAG pipeline (vector search + BM25 keyword + Reciprocal Rank Fusion).
- [x] C1–C18 intent classification, entity extraction, and ambiguity detection.
- [x] Deterministic routing matrix with priority-based decision logic.
- [x] Result checking and evidence sufficiency gatekeeper.
- [x] Answer generator with locked evidence prompt templates.
- [x] Post-generation deterministic draft validator for fact safety.
- [x] Dependency injection architecture decoupling tests from external services.
- [x] 164 automated tests passing with 0 failures and 0 warnings.

### Pending / In-Progress
- [ ] Active local/hosted Ollama daemon startup (`ollama serve` + `ollama pull qwen3:8b`) for live local LLM answer generation in development.
- [ ] Cloud deployment infrastructure (e.g. Google Cloud Run / Docker containerization with production PostgreSQL).

---

## 19. Production Readiness & Remaining Work

1. **Local Ollama Daemon**: Start Ollama locally with `ollama serve` and pull `qwen3:8b` to enable live LLM synthesis during manual local testing.
2. **Production Database & Vector Storage**: Deploy to hosted PostgreSQL (e.g., Supabase / Cloud SQL) and run `alembic upgrade head` followed by `scripts.seed_structured_data`.
3. **Containerization**: Package the FastAPI service into a production Docker image using standard multi-stage builds.

---

## 20. Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/Involynk/PERC-Automation.git
cd PERC-Automation

# 2. Virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run tests
pytest -q

# 5. Start development API server
uvicorn app.main:app --reload
```

---

*Authored for the PERC Response Service Architecture & Engineering Team.*
