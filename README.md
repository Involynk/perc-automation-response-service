# PERC Response Service

> **Deterministic, Fact-Grounded, Hybrid AI Response Service for Educational Inquiries**

The **PERC Response Service** is a high-reliability, production-ready AI query-answering engine engineered specifically for the PERC educational institute. It processes prospective and enrolled student/parent inquiries across course discovery, syllabus details, fee structures, center locations, eligibility criteria, admission milestones, batch seat availability, and institutional policies.

The service combines **deterministic PostgreSQL relational database tools** with **hybrid semantic RAG knowledge retrieval** in a compiled **LangGraph multi-stage pipeline** exposed through a **FastAPI** web service. It enforces strict fact-protection guardrails against hallucinated fee and seat figures, and synthesizes answers via local **Ollama (Qwen3:8B)** or deterministic test providers.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Complete Architecture](#2-complete-architecture)
3. [LangGraph Pipeline Nodes](#3-langgraph-pipeline-nodes)
4. [Query Understanding (C1–C18)](#4-query-understanding-c1c18)
5. [Deterministic Routing Logic](#5-deterministic-routing-logic)
6. [Structured Data Layer & Tools](#6-structured-data-layer--tools)
7. [RAG Knowledge Layer & Authority Rules](#7-rag-knowledge-layer--authority-rules)
8. [Result Check & Evidence Verification](#8-result-check--evidence-verification)
9. [Answer Generation with Qwen3:8B](#9-answer-generation-with-qwen38b)
10. [Draft Validation & Safety Guardrails](#10-draft-validation--safety-guardrails)
11. [FastAPI API Specifications](#11-fastapi-api-specifications)
12. [Configuration & Environment Modes](#12-configuration--environment-modes)
13. [Local Development & Operations](#13-local-development--operations)
14. [Testing & Verification](#14-testing--verification)
15. [Production Architecture & Deployment Notes](#15-production-architecture--deployment-notes)
16. [Security Guidelines](#16-security-guidelines)
17. [Project Directory Layout](#17-project-directory-layout)
18. [Development Status & Roadmap](#18-development-status--roadmap)

---

## 1. Project Overview

### What the Service Does
The PERC Response Service sits at the core of PERC's automated communications. When students or parents ask questions via web or chat interfaces, this service:
1. **Understands Intent & Entities**: Accurately classifies user queries into one of 18 canonical intent categories (C1–C18) and extracts relevant academic entities (courses, exams, target classes, branches).
2. **Identifies Ambiguity**: Clarifies incomplete queries before attempting retrieval.
3. **Routes Strategically**: Chooses between deterministic relational database lookup, hybrid RAG knowledge search, multi-intent decomposition, human escalation, or safe stops.
4. **Executes Securely**: Invokes read-only structured tools against PostgreSQL / Supabase or retrieves authoritative markdown chunks.
5. **Verifies Evidence**: Evaluates whether retrieved data is sufficient and conflict-free prior to LLM invocation.
6. **Generates Grounded Answers**: Synthesizes clear, student-friendly responses exclusively from verified evidence using Ollama Qwen3:8B.
7. **Validates Drafts Deterministically**: Scans generated drafts for ungrounded numbers, unsupported claims, or missing disclaimers.
8. **Delivers Standard Contracts**: Returns clean, user-facing `ResponseResponse` payloads with explicit sources and status tags.

### Purpose of the Hybrid Architecture
Standard pure-LLM chatbots suffer from non-deterministic hallucination, which is unacceptable for institutional fee disclosures, eligibility constraints, and seat quotas. Pure search engines, conversely, lack conversational synthesis. The **Hybrid Response Service** solves this by:
- Storing **hard quantitative facts** (fees, batch sizes, prerequisites, center details) in **PostgreSQL relational tables** accessed via locked, typed tools.
- Storing **pedagogical, descriptive, and policy context** (scholarship rules, refund terms, curriculum details) in a **hybrid vector/keyword RAG index**.
- Using **Qwen3:8B strictly as a synthesis engine** bounded by verified retrieval evidence.

---

## 2. Complete Architecture

```text
Client Application
  ↓
FastAPI Web Server
  ↓
Response API (/api/v1/response, /response)
  ↓
LangGraph Response Pipeline
  ↓
Initialize Node
  ↓
Query Understanding Node (MockDataProvider / LLMQueryProvider via Ollama Qwen3:8B)
  ↓
Ambiguity Detection Node
  ↓
Routing Node (Deterministic Decision Matrix)
  ↓
Execution Node
  ├── Structured Tools → StructuredDataService → PostgreSQL / Supabase
  └── RAG Retrieval → Hybrid Knowledge Retriever → pgvector + BM25 + RRF
  ↓
Result Check Node (Deterministic Evidence Gatekeeper)
  ↓
Qwen3 Answer Generation Node (AnswerGenerator with Evidence-Locked Prompt)
  ↓
Draft Validation Node (Fact & Guardrail Scanner)
  ↓
ResponseResponse Schema
  ↓
Client Application
```

---

## 3. LangGraph Pipeline Nodes

The compiled `StateGraph` in `app/agent/graph.py` executes 8 discrete, sequential nodes:

1. **`initialize`** (`app/agent/nodes/initialize.py`):
   - Validates `session_id` and query `message`.
   - Initializes a clean `AgentState` and ingests optional conversation context (`state.metadata["conversation_context"]`).
2. **`understand`** (`app/agent/nodes/understand.py`):
   - Invokes the configured query understanding provider (`MockDataProvider` in tests or `LLMQueryProvider` in production).
   - Populates `state.intent`, `state.secondary_intents`, `state.entities`, and `state.ambiguity`.
3. **`ambiguity`** (`app/agent/nodes/ambiguity.py`):
   - Evaluates whether the query lacks essential parameters (e.g., asking for fees without specifying a course).
   - Flags `clarification_required = True` and sets a contextual `clarification_question`.
4. **`routing`** (`app/agent/nodes/routing.py`):
   - Executes deterministic decision logic (`decide_routing`) across C1–C18 categories.
   - Selects route: `STRUCTURED_TOOL`, `RAG`, `MULTI_INTENT`, `CLARIFICATION`, `HUMAN_HANDOFF`, or `SAFE_STOP`.
5. **`execution`** (`app/agent/nodes/execution.py`):
   - Executes the chosen route via `ExecutionEngine`.
   - Calls read-only Structured Tools against `StructuredDataService` or performs hybrid retrieval over Markdown documents.
   - Populates `state.tool_results` and `state.retrieved_documents`.
6. **`result_check`** (`app/agent/nodes/result_check.py`):
   - Evaluates whether retrieved evidence is sufficient, relevant, and free of contradictions.
   - Dictates whether the pipeline proceeds to answer generation or fallbacks gracefully to human counseling.
7. **`generation`** (`app/agent/nodes/generation.py`):
   - Formats locked evidence and prompts `AnswerGenerator` (Ollama Qwen3:8B).
   - Bypasses LLM generation if evidence is missing or if query is ambiguous/escalated.
8. **`result_validation`** (`app/agent/nodes/result_validation.py`):
   - Scans generated draft answers for ungrounded fees, seat counts, or hallucinated claims.
   - Sets final validation status (`validated` or `escalated`).

---

## 4. Query Understanding (C1–C18)

The system classifies student and parent queries into 18 canonical intent categories:

| Code | Intent Category | Description | Sample Query |
|---|---|---|---|
| **C1** | `C1_COURSE_DISCOVERY` | General inquiry on offerings | *"What courses do you offer at PERC?"* |
| **C2** | `C2_COURSE_DETAILS` | Specific course curriculum & duration | *"Tell me about the 2-Year JEE Advanced program."* |
| **C3** | `C3_FEES_PRICING` | Program fees & payment schedules | *"How can I find the fee structure for NEET UG?"* |
| **C4** | `C4_ELIGIBILITY` | Class & prerequisite requirements | *"Who can join the NEET Foundation program?"* |
| **C5** | `C5_BRANCH_LOCATION` | Center addresses & phone numbers | *"Where is the PERC center located?"* |
| **C6** | `C6_ADMISSION_PROCESS` | Step-by-step onboarding | *"How do I enroll at PERC?"* |
| **C7** | `C7_REQUIRED_DOCUMENTS`| Certificates & verification documents| *"What documents are needed for admission?"* |
| **C8** | `C8_POLICIES` | Batch sizes, refund & transfer rules | *"What is your batch size and refund policy?"* |
| **C9** | `C9_AVAILABILITY_STATUS`| Seat status & enrollment windows | *"Are admissions currently open for Class 11?"* |
| **C10**| `C10_COMPARISON` | PERC methodology vs. other institutes| *"How is PERC different from large national chains?"* |
| **C11**| `C11_MULTI_INTENT` | Queries combining multiple topics | *"What is the fee for JEE and what documents are needed?"*|
| **C12**| `C12_FOLLOW_UP_CONTEXTUAL`| Context-dependent follow-up queries | *"What time are the classes for that batch?"* |
| **C13**| `C13_AMBIGUOUS_INCOMPLETE`| Under-specified queries | *"What is the fee?"* (no course specified) |
| **C14**| `C14_OUT_OF_SCOPE_ESCALATION`| Non-institutional / competitive queries| *"Which coaching is better, PERC or Allen?"* |
| **C15**| `C15_GRIEVANCE_HUMAN_HANDOFF`| Complaints & escalation | *"I want to lodge a complaint about my batch teacher."* |
| **C16**| `C16_HOSTEL_ACCOMMODATION`| Accommodation facilities | *"Do you have hostel facilities for outstation students?"*|
| **C17**| `C17_PLACEMENT_CAREER_OUTCOMES`| Historical ranks & results | *"What are your historical student JEE ranks?"* |
| **C18**| `C18_LANGUAGE_MEDIUM` | Medium of instruction | *"Is instruction in English or bilingual?"* |

### Providers
- **`MockDataProvider`**: Deterministic provider for fast, reliable CI and unit test execution without external services.
- **`LLMQueryProvider`**: Production provider using Ollama Qwen3:8B. Converts query + context into structured JSON containing `primary_intent`, `secondary_intents`, `entities`, `ambiguity`, and `confidence`.

---

## 5. Deterministic Routing Logic

The routing engine (`app/agent/router.py`) enforces strict priority rules:

```text
Priority Hierarchy:
Human Handoff (C15) > Ambiguity / Clarification (C13) > Safe Stop (C14) > Multi-Intent (C11) > Structured Tools (C1-C6, C9) > RAG (C7, C8, C10, C16-C18)
```

| Category | Primary Route | Selected Tool / Target | Action Taken |
|---|---|---|---|
| **C1** (Course Discovery) | `STRUCTURED_TOOL` | `get_course_info` | Queries course catalog in PostgreSQL |
| **C2** (Course Details) | `STRUCTURED_TOOL` | `get_course_info` | Retrieves official course specifications |
| **C3** (Fees & Pricing) | `STRUCTURED_TOOL` | `get_fee` | Retrieves locked tuition/fee figures |
| **C4** (Eligibility) | `STRUCTURED_TOOL` | `get_eligibility` | Evaluates grade and prerequisite rules |
| **C5** (Branch Location) | `STRUCTURED_TOOL` | `get_branch_info` | Retrieves center addresses and contacts |
| **C6** (Admission Process) | `STRUCTURED_TOOL` | `get_admission_steps` | Retrieves standard enrollment steps |
| **C7** (Required Documents)| `RAG` | `required-documents.md` | Retrieves document checklists |
| **C8** (Policies) | `RAG` | `policies.md` | Retrieves batch size and refund clauses |
| **C9** (Availability) | `STRUCTURED_TOOL` | `get_availability` / `get_admission_status` | Checks seat status and enrollment state |
| **C10** (Comparison) | `RAG` | `comparison.md` | Retrieves pedagogical differentiators |
| **C11** (Multi-Intent) | `MULTI_INTENT` | Decomposed Sub-routes | Executes parallel/sequential sub-intents |
| **C12** (Follow-Up) | `CONTEXTUAL` | Context Disambiguation | Resolves context or asks clarification |
| **C13** (Ambiguous) | `CLARIFICATION` | No Tool Execution | Formulates clarification question |
| **C14** (Out-of-Scope) | `SAFE_STOP` | No Tool Execution | Escalate safely to admissions team |
| **C15** (Grievance) | `HUMAN_HANDOFF` | No Tool Execution | Escalates immediately to counseling |
| **C16** (Hostel) | `RAG` | `hostel-accommodation.md` | Retrieves hostel/accommodation rules |
| **C17** (Outcomes) | `RAG` | `placement-career-outcomes.md`| Retrieves historical ranks & disclaimers |
| **C18** (Language) | `RAG` | `language-medium.md` | Retrieves language medium details |

---

## 6. Structured Data Layer & Tools

### Relational Tables (PostgreSQL / Supabase)
1. **`courses`**: Course ID, name, duration, target class, target exam, batch size, subjects, status.
2. **`branches`**: Branch ID, name, address, city, phone, email, operating hours.
3. **`fees`**: Program ID, registration fee, tuition fee, installment plans, refund policy notes.
4. **`eligibility`**: Program name, minimum class, maximum class, prerequisites, academic criteria.
5. **`availability`**: Program ID, batch name, total seats, filled seats, waitlist status.
6. **`admission_status`**: Global admission status, academic year, active batch start dates.

### 7 Read-Only Structured Tools (`app/tools/structured/`)
- `get_course_info(course_id, name, target_class, exam)`
- `get_fee(course_id, course_name)`
- `get_branch_info(branch_id, name, city)`
- `get_eligibility(program_name, course_id, target_class)`
- `get_admission_steps(program_name)`
- `get_admission_status()`
- `get_availability(program_id, batch_name)`

> [!IMPORTANT]
> **Strict Architectural Rule**: Structured tools ONLY call `StructuredDataService`. They **never** execute raw SQL, never manage SQLAlchemy sessions directly, never invoke LLM prompts, and never perform free-form natural language generation.

---

## 7. RAG Knowledge Layer & Authority Rules

### Ingestion & Chunking (`app/rag/`)
- **18 Knowledge Documents** in `MockData/unstructured/` covering institutional policies, pedagogy, comparisons, language medium, and FAQs.
- **Hierarchical Markdown Chunking**: Chunks by Markdown headers (`H1` -> `H2` -> `H3`), preserving tables and bulleted lists intact with deterministic IDs (`doc_name#chunk_index`).
- **Hybrid Retrieval**:
  - **Vector Semantic Search**: Cosine similarity against 384-dimensional embeddings (or pgvector in production).
  - **Keyword BM25 Search**: Exact keyword match over terms and course aliases.
  - **Reciprocal Rank Fusion (RRF)**: Merges vector and keyword scores ($RRF\_Score = \sum \frac{1}{60 + rank}$) for optimal precision.

### Authority Hierarchy
```text
Tier 1: PostgreSQL Relational Database (Absolute Authority for numeric/policy/seat facts)
  > Tier 2: Unstructured Markdown Knowledge Base (Descriptive/Pedagogical Context)
    > Tier 3: LLM Parametric Knowledge (Zero Authority for institutional facts)
```
When facts overlap (e.g. course duration or branch location), structured database results strictly supersede RAG text snippets.

---

## 8. Result Check & Evidence Verification

The `result_check_node` (`app/agent/nodes/result_check.py` and `app/agent/result_checker.py`) acts as a deterministic evidence gate:
- Verifies that tool results are marked `success=True` and contain non-empty data payloads.
- Verifies that RAG retrieval scores exceed the relevance threshold.
- Detects factual contradictions between multiple retrieved documents.
- If evidence is insufficient, skips LLM generation and routes cleanly to `status="escalated"` with guidance to contact admissions.

---

## 9. Answer Generation with Qwen3:8B

Answer generation (`app/agent/generator.py` and `app/agent/nodes/generation.py`) synthesizes verified evidence into natural language:
- **Evidence-Locked Prompts**: The prompt explicitly restricts the LLM to facts present in the provided `STRUCTURED_RESULTS` and `RAG_RESULTS` JSON blocks.
- **Zero Extrapolation**: The model is forbidden from inventing fees, installment plans, dates, or contact details not present in the evidence.
- **Output Contract**: Generates a strictly validated `DraftAnswerModel` JSON payload.

---

## 10. Draft Validation & Safety Guardrails

The Phase 5G validation node (`app/agent/result_validator.py` and `app/agent/nodes/result_validation.py`) enforces safety before responses leave the engine:
- **Fee Guardrail**: Scans the text for currency symbols and numeric amounts, verifying that each number matches retrieved structured fee records.
- **Seat Availability Guardrail**: Prevents claiming seats are available unless verified via `get_availability`.
- **Competitor/Comparison Guardrail**: Verifies comparisons adhere strictly to `comparison.md` without derogatory claims.
- **Status Assignment**: Sets `status="success"` for valid answers, or flags anomalies for human counseling review.

---

## 11. FastAPI API Specifications

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness & readiness probe |
| `POST` | `/api/v1/response` | Primary response generation endpoint |
| `POST` | `/response` | Direct root-mounted response endpoint |

### Request Contract (`ResponseRequest`)
```json
POST /api/v1/response
Content-Type: application/json

{
  "session_id": "sess-student-8921",
  "message": "What is the fee for the Class 11 IIT-JEE Advanced program?",
  "metadata": {}
}
```

### Standard Response Contract (`ResponseResponse`)
```json
HTTP/200 OK
Content-Type: application/json

{
  "session_id": "sess-student-8921",
  "answer": "The fee structure for the Class 11 IIT-JEE Advanced program includes a registration fee and tuition fee as detailed in our official fee schedule.",
  "status": "success",
  "intent": "C3_FEES_PRICING",
  "sources": [
    "structured_database"
  ],
  "clarification_required": false,
  "clarification_question": null
}
```

### Clarification Response Contract
```json
HTTP/200 OK
Content-Type: application/json

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

## 12. Configuration & Environment Modes

Managed via `app/core/config.py` using `.env`:

```ini
# Database Connection (PostgreSQL / Supabase)
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/perc_db

# Application Environment ('development' or 'production')
ENVIRONMENT=development

# Query Understanding Provider: 'mock' (default for fast CI) or 'llm' (production)
QUERY_UNDERSTANDING_PROVIDER=llm

# LLM Provider Configuration
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_TEMPERATURE=0.0

# Ollama Local Service Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT=180
```

### Mode Differences
- **`mock` Mode (`QUERY_UNDERSTANDING_PROVIDER=mock`)**: Uses `MockDataProvider` and deterministic fixtures for ultra-fast, offline unit and integration testing without requiring GPU/Ollama.
- **`llm` Mode (`QUERY_UNDERSTANDING_PROVIDER=llm`)**: Uses `LLMQueryProvider` and `OllamaLLMClient` with `qwen3:8b` for live AI query classification and answer generation.

---

## 13. Local Development & Operations

### 1. Install Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Start Ollama & Pull Qwen3 Model
```bash
# Start Ollama service (in separate terminal)
ollama serve

# Pull Qwen3:8B model
ollama pull qwen3:8b

# Verify model presence
ollama list
```

### 3. Run Diagnostic Smoke Test
```bash
python -m scripts.test_ollama_connection
```

### 4. Run Test Suite
```bash
# Run deterministic test suite (164 tests)
pytest -q -m "not live"

# Run live Qwen3 E2E verification
pytest tests/agent/test_real_e2e.py -m live -k "live-C1-001 or live-C3-001" -v
```

### 5. Start FastAPI Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 14. Testing & Verification

The test suite enforces rigorous separation between deterministic tests and live LLM tests:

- **Deterministic Tests (`tests/conftest.py`)**: Automatically isolate `QUERY_UNDERSTANDING_PROVIDER` to `mock` so that all 164 unit and integration tests run fast and offline.
- **Live Tests (`@pytest.mark.live`)**: Exercise the live pipeline end-to-end through FastAPI, LangGraph, and the running Ollama Qwen3 model.

### Current Verification Status
- **Deterministic Tests**: **164 passed**, 0 failures, 0 warnings
- **Live Qwen3 Tests**: **C1 (Course Discovery) passed**, **C3 (Fees/Pricing) passed**
- **Deprecation Warnings**: **0**

---

## 15. Production Architecture & Deployment Notes

```text
+-----------------------+      HTTP REST      +-----------------------+
|  FastAPI App Service  | ------------------> |  Ollama Qwen3:8B Daemon|
|  (Stateless Container)|                     |  (GPU Compute Node)   |
+-----------+-----------+                     +-----------------------+
            |
            | SQLAlchemy / psycopg
            v
+-----------------------+
|  PostgreSQL Database  |
|  (Supabase / pgvector)|
+-----------------------+
```

### Architectural Separation
- **FastAPI Response Service**: Stateless container that handles API requests, orchestrates LangGraph state, and executes tools.
- **PostgreSQL / Supabase**: Stores relational institutional data and pgvector embeddings.
- **Ollama / Qwen3:8B**: Hosted on a dedicated GPU instance/service. **Ollama should NOT be embedded inside the FastAPI Docker container.** It communicates via standard HTTP API (`OLLAMA_BASE_URL`).

---

## 16. Security Guidelines

1. **Environment Secrets**: Secrets and credentials must reside in `.env` or cloud secret managers. Never hardcode passwords, database URLs, or API keys in source files.
2. **`.gitignore` Enforcement**: `.env` and local cache directories must never be committed to Git.
3. **No Database Credentials in README**: Always use placeholder URLs in documentation.
4. **Zero-Trust LLM Fact Authority**: The LLM is never trusted as an authoritative source of facts. All numeric figures and institutional claims must be anchored in structured database or verified RAG evidence.

---

## 17. Project Directory Layout

```text
d:\response-service\
├── alembic/                      # Database migrations (PostgreSQL)
│   └── versions/                 # Migration scripts for 6 relational tables
├── app/
│   ├── agent/                    # LangGraph multi-node engine
│   │   ├── nodes/                # 8 discrete pipeline node implementations
│   │   │   ├── initialize.py     # State initialization node
│   │   │   ├── understand.py     # Intent & entity classification node
│   │   │   ├── ambiguity.py      # Ambiguity detection node
│   │   │   ├── routing.py        # Deterministic routing node
│   │   │   ├── execution.py      # Tools & RAG execution node
│   │   │   ├── result_check.py   # Evidence verification node
│   │   │   ├── generation.py     # Answer generation node
│   │   │   └── result_validation.py # Draft fact validation node
│   │   ├── prompts/              # System prompts for Qwen3 (understanding & generation)
│   │   ├── providers/            # Mock & LLM providers, Ollama client
│   │   ├── executor.py           # ExecutionEngine for tools and retrieval
│   │   ├── generator.py          # AnswerGenerator
│   │   ├── graph.py              # Compiled LangGraph definition
│   │   ├── result_checker.py     # Evidence sufficiency checker
│   │   ├── result_validator.py   # Deterministic draft validator
│   │   └── router.py             # C1–C18 routing logic
│   ├── api/                      # FastAPI layer
│   │   ├── deps.py               # Dependency injection (get_response_graph)
│   │   └── v1/                   # API v1 routes & endpoints
│   ├── core/
│   │   └── config.py             # Pydantic BaseSettings
│   ├── db/
│   │   ├── models/               # SQLAlchemy models (courses, fees, branches, etc.)
│   │   ├── base.py               # DeclarativeBase
│   │   └── session.py            # Sessionmaker & DB engine
│   ├── rag/                      # Hybrid RAG pipeline
│   │   ├── chunker.py            # Hierarchical markdown chunking
│   │   ├── loader.py             # Document loader
│   │   ├── metadata.py           # Document metadata extractor
│   │   ├── retriever.py          # Vector/keyword hybrid retriever
│   │   └── vector_store.py       # Embedding indexer
│   ├── repositories/             # Relational database repositories
│   ├── schemas/                  # Pydantic schemas (Request, Response, AgentState)
│   ├── services/                 # StructuredDataService
│   ├── tools/                    # 7 read-only structured tools
│   └── main.py                   # FastAPI application entrypoint
├── docs/                         # Architecture documentation
├── MockData/                     # Authoritative institutional mock data
│   ├── structured/               # JSON datasets (courses, fees, branches, etc.)
│   └── unstructured/             # 18 Markdown knowledge base documents
├── scripts/                      # Operational & verification scripts
│   ├── check_table_counts.py     # Verify DB row counts
│   ├── ingest_knowledge.py       # RAG knowledge base ingestion
│   ├── seed_structured_data.py   # Seed PostgreSQL tables from MockData
│   └── test_ollama_connection.py # Diagnostic smoke test for Ollama
├── tests/                        # Automated test suite (164 deterministic + live tests)
│   ├── conftest.py               # Global pytest fixtures & provider isolation
│   └── agent/test_real_e2e.py    # Real end-to-end verification tests
├── alembic.ini                   # Alembic configuration
├── pytest.ini                    # Pytest configuration & markers
└── requirements.txt              # Project dependencies
```

---

## 18. Development Status & Roadmap

### Implemented & Verified
- [x] **Phase 1**: Request/Response and State Contracts (`ResponseRequest`, `ResponseResponse`, `AgentState`).
- [x] **Phase 2**: Relational PostgreSQL data model (6 tables) and Alembic migrations.
- [x] **Phase 3**: 7 read-only typed structured tools invoking `StructuredDataService`.
- [x] **Phase 4**: Hybrid RAG pipeline (vector search + BM25 keyword + Reciprocal Rank Fusion).
- [x] **Phase 5A–5G**: 8-node LangGraph pipeline (understanding, ambiguity, routing, execution, result check, generation, validation).
- [x] **Phase 5H**: FastAPI integration (`POST /api/v1/response`) and live Ollama Qwen3:8B verification (C1 and C3).
- [x] **164 Deterministic Tests Passing** with 0 failures and 0 warnings.

### Next Stage (Production Deployment)
- [ ] Docker containerization for the stateless FastAPI service.
- [ ] Production PostgreSQL & pgvector deployment.
- [ ] Dedicated GPU deployment for Ollama Qwen3:8B inference.
- [ ] CI/CD pipeline integration.

---

*Authored for the PERC Response Service Engineering Team.*
