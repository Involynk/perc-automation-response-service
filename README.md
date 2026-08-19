# PERC Response Service

> **Deterministic, Fact-Grounded, Hybrid AI Response Service & Universal Response Composer for Educational Inquiries**

The **PERC Response Service** is a high-reliability, production-grade AI query-answering engine engineered specifically for the PERC educational institute. It processes prospective and enrolled student/parent inquiries across course discovery, syllabus details, fee structures, center locations, eligibility criteria, admission milestones, batch seat availability, and institutional policies.

The service combines **authoritative PostgreSQL relational database tools** with **hybrid semantic RAG knowledge retrieval** in a compiled **LangGraph multi-stage pipeline** exposed through a **FastAPI** web service. It enforces strict fact-protection guardrails against hallucinated fee and seat figures, separates retrieval from presentation via a dedicated **Universal Response Composer**, and synthesizes customer-friendly, WhatsApp-compatible responses.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Complete Architecture](#2-complete-architecture)
3. [Universal Response Composer Layer](#3-universal-response-composer-layer)
4. [Hybrid Query Understanding & Fast Path](#4-hybrid-query-understanding--fast-path)
5. [LangGraph Pipeline Nodes](#5-langgraph-pipeline-nodes)
6. [Query Understanding (C1–C18)](#6-query-understanding-c1c18)
7. [Deterministic Routing Logic](#7-deterministic-routing-logic)
8. [Structured Data Layer & Tools](#8-structured-data-layer--tools)
9. [RAG Knowledge Layer & Authority Rules](#9-rag-knowledge-layer--authority-rules)
10. [Result Check & Evidence Verification](#10-result-check--evidence-verification)
11. [Draft Validation & Safety Guardrails](#11-draft-validation--safety-guardrails)
12. [FastAPI API Specifications](#12-fastapi-api-specifications)
13. [Configuration & Environment Modes](#13-configuration--environment-modes)
14. [Local Development & Operations](#14-local-development--operations)
15. [Testing & Verification](#15-testing--verification)
16. [Production Deployment Checklist](#16-production-deployment-checklist)
17. [Project Directory Layout](#17-project-directory-layout)

---

## 1. Project Overview

### What the Service Does
The PERC Response Service sits at the core of PERC's automated student communications. When students or parents ask questions via web or chat interfaces (such as WhatsApp), this service:
1. **Understands Intent & Entities**: Accurately classifies user queries into one of 18 canonical intent categories (C1–C18) and extracts relevant academic entities (courses, exams, target classes, branches).
2. **Deterministic Fast Path (< 1ms)**: Automatically resolves common queries (all courses list, course details, fees, branches, greetings) without invoking expensive LLMs.
3. **Routes Strategically**: Chooses between deterministic relational database lookup, hybrid RAG knowledge search, multi-intent decomposition, human escalation, or safe stops.
4. **Executes Securely**: Invokes read-only structured tools against PostgreSQL / Supabase or retrieves authoritative markdown chunks via pgvector.
5. **Verifies Evidence**: Evaluates whether retrieved data is sufficient and conflict-free prior to answer generation.
6. **Universal Response Composition**: Formats verified facts into concise, friendly, WhatsApp-ready markdown with bullets, bold names, and follow-up guidance.
7. **Zero Hallucination Guarantee**: Fact-protection guardrails prevent hallucination of numeric fees, discount schemes, or seat counts.
8. **Delivers Standard Contracts**: Returns clean, user-facing `ResponseResponse` payloads with explicit sources and status tags.

---

## 2. Complete Architecture

```text
Student Enquiry / Client Application
              │
              ▼
┌────────────────────────────────────────────────────────┐
│ FastAPI Web Service (POST /api/v1/response)            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ LangGraph StateGraph Orchestrator                      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Query Understanding (Fast-Path Rules + Ollama fallback)│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Tool Selection & Execution                             │
│ ├── Structured Database Tools (PostgreSQL / Supabase)  │
│ └── Hybrid RAG Retrieval (pgvector + BM25 + RRF)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Deterministic Evidence Check & Verification Gate       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 🔹 Universal Response Composer / Formatter             │
│ • Intent-aware customer presentation                   │
│ • WhatsApp-friendly bullets and bold highlights        │
│ • 0 LLM calls for structured database facts            │
│ • Grounded RAG synthesis for descriptive knowledge     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Response Guard & Validator (PII, Grounding, Policy)    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
                  Final API Response
```

---

## 3. Universal Response Composer Layer

The **Universal Response Composer** (`app/agent/composer.py`) completely decouples **data retrieval** from **customer-facing presentation**:

- **Predictable Normalization**: Normalizes database tool records and RAG document chunks into a unified `NormalizedResult`.
- **WhatsApp Compatibility**: Formats output with short paragraphs, scannable bullet points (`•`), bold entity titles, and friendly next-step prompts.
- **Zero Hallucination / Fact Grounding**: Uses only verified database values. If a course fee is listed as *"Contact for price"*, the composer accurately informs the student without guessing a numeric price.
- **Zero Technical Leakage**: Never exposes internal metadata such as `"structured_database"`, `"C1_COURSE_DISCOVERY"`, or internal tool names in the customer answer.

---

## 4. Hybrid Query Understanding & Fast Path

`app/agent/providers/hybrid_provider.py` implements a 2-tier hybrid classification engine:

1. **Deterministic Fast Path (< 1ms)**:
   - Matches known course names (14 PERC programs), branches, keywords, and patterns.
   - Handles course discovery, course details, fees, eligibility, branches, greetings, and safe escalations with **0 LLM calls**.
2. **LLM Fallback (Ollama `qwen3:8b`)**:
   - Handles nuanced, multi-part, or conversational queries.
   - Constrained with native JSON formatting (`format="json"`), `num_predict: 256`, and a 15-second hard timeout.

---

## 5. LangGraph Pipeline Nodes

The compiled `StateGraph` in `app/agent/graph.py` executes 8 discrete, sequential nodes:

1. **`initialize`** (`app/agent/nodes/initialize.py`): Validates session and initializes clean `AgentState`.
2. **`understand`** (`app/agent/nodes/understand.py`): Classifies intent and extracts entities via hybrid provider.
3. **`ambiguity`** (`app/agent/nodes/ambiguity.py`): Detects under-specified queries and prepares clarification prompts.
4. **`routing`** (`app/agent/nodes/routing.py`): Executes deterministic routing decision across C1–C18 categories.
5. **`execution`** (`app/agent/nodes/execution.py`): Invokes read-only structured tools or RAG vector search.
6. **`result_check`** (`app/agent/nodes/result_check.py`): Verifies evidence sufficiency, coverage, and consistency.
7. **`generation`** (`app/agent/nodes/generation.py`): Delegates to `ResponseComposer` for intent-aware presentation.
8. **`result_validation`** (`app/agent/nodes/result_validation.py`): Scans output for grounding, policy, and safety compliance.

---

## 6. Query Understanding (C1–C18)

| Code | Intent Category | Description | Routing Action |
|---|---|---|---|
| **C1** | `C1_COURSE_DISCOVERY` | General catalog inquiry | Structured Tool (`get_course_info`) |
| **C2** | `C2_COURSE_DETAILS` | Course curriculum & duration | Structured Tool (`get_course_info`) |
| **C3** | `C3_FEES_PRICING` | Program fees & payment policy | Structured Tool (`get_fee`) |
| **C4** | `C4_ELIGIBILITY` | Class & prerequisite requirements | Structured Tool (`get_eligibility`) |
| **C5** | `C5_BRANCH_LOCATION` | Center addresses & contacts | Structured Tool (`get_branch_info`) |
| **C6** | `C6_ADMISSION_PROCESS` | Step-by-step enrollment steps | Structured Tool (`get_admission_steps`) |
| **C7** | `C7_REQUIRED_DOCUMENTS`| Certificates & document checklists | RAG Search (`required-documents.md`) |
| **C8** | `C8_POLICIES` | Institutional rules & concessions | RAG Search (`policies.md`) |
| **C9** | `C9_AVAILABILITY_STATUS`| Seat status & enrollment windows | Structured Tool (`get_availability`) |
| **C10**| `C10_COMPARISON` | PERC pedagogical differentiators | RAG Search (`comparison.md`) |
| **C11**| `C11_MULTI_INTENT` | Queries combining multiple topics | Sub-intent decomposition |
| **C12**| `C12_FOLLOW_UP_CONTEXTUAL`| Context-dependent follow-up queries | Disambiguation / Context lookup |
| **C13**| `C13_AMBIGUOUS_INCOMPLETE`| Under-specified queries | Polite Clarification Prompt |
| **C14**| `C14_OUT_OF_SCOPE_ESCALATION`| Non-institutional questions | Safe Referral to Admissions |
| **C15**| `C15_GRIEVANCE_HUMAN_HANDOFF`| Complaints & escalation | Immediate Human Desk Routing |
| **C16**| `C16_HOSTEL_ACCOMMODATION`| Accommodation facilities | RAG Search (`hostel-accommodation.md`) |
| **C17**| `C17_PLACEMENT_CAREER_OUTCOMES`| Historical ranks & results | RAG Search (`placement-career-outcomes.md`) |
| **C18**| `C18_LANGUAGE_MEDIUM` | Medium of instruction | RAG Search (`language-medium.md`) |

---

## 7. Structured Data Layer & Tools

### Relational Tables (PostgreSQL / Supabase)
1. **`resp_courses`**: 14 official programs (Ignite, Explorer, Challenger, Achiever, Champion, NEET, JEE, KCET, CBSE, ICSE, Olympiad, 1-to-1).
2. **`resp_branches`**: Learning centers (Ujire, Begur/Bangalore).
3. **`resp_fee_policies` & `resp_program_fees`**: Official pricing policies and course fee records.
4. **`resp_eligibility_policies` & `resp_program_eligibility`**: Grade prerequisites and eligibility rules.
5. **`resp_availability_info` & `resp_admission_statuses`**: Seat limit and batch availability statuses.

### 7 Read-Only Structured Tools (`app/tools/structured/`)
- `get_course_info(course_id, course_name, target_class, exam)`
- `get_fee(course_id, course_name)`
- `get_branch_info(branch_id, branch_name)`
- `get_eligibility(program_name, course_id, target_class)`
- `get_admission_steps()`
- `get_admission_status()`
- `get_availability()`

---

## 8. FastAPI API Specifications

### Primary Endpoint
```http
POST /api/v1/response
Content-Type: application/json

{
  "session_id": "student_001",
  "message": "What courses do you offer?",
  "metadata": { "channel": "whatsapp" }
}
```

### Standard Response Contract
```json
{
  "session_id": "student_001",
  "answer": "Hi! 👋 PERC offers comprehensive coaching across school academics, competitive exams, and foundational learning.\n\n**Available Programs:**\n• **PERC Ignite** – Class 6\n• **PERC Explorer** – Class 7\n• **PERC Challenger** – Class 8\n• **PERC Achiever** – Class 9\n• **PERC Champion** – Class 10\n• **NEET Foundation** – Classes 9-10\n• **NEET UG** – Classes 11-12 & Aspirants\n• **JEE Foundation** – Classes 9-10\n• **IIT-JEE Advanced** – Classes 11-12 & Aspirants\n• **KCET Crash Course** – Class 12 & Aspirants\n• **CBSE Board Coaching** – Classes 10-12\n• **ICSE Board Coaching** – Classes 9-10\n• **Olympiad Foundation** – Classes 6-10\n• **One-to-One Tuition** – Personalized coaching (All classes)\n\nWhich class or exam are you preparing for? I can provide specific details on eligibility, subjects, duration, and fees!",
  "status": "success",
  "intent": "C1_COURSE_DISCOVERY",
  "sources": [
    "structured_database"
  ],
  "clarification_required": false,
  "clarification_question": null
}
```

---

## 9. Local Development & Operations

### 1. Install Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
```ini
DATABASE_URL=postgresql+psycopg://postgres:<PASSWORD>@<HOST>:5432/<DB>
QUERY_UNDERSTANDING_PROVIDER=hybrid
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT=15
```

### 3. Run Automated Tests
```bash
# Run complete deterministic test suite (192 tests)
pytest -q -m "not live"
```

### 4. Start FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 10. Testing & Verification

- **Automated Pytest Suite**: **192 passed**, 0 failures, 0 warnings.
- **Coverage**:
  - Universal Response Composer (`test_response_composer.py`): 9 tests covering discovery, fees, branches, eligibility, admission steps, greetings, fallbacks.
  - Hybrid Fast-Path Classifier (`test_hybrid_fast_path.py`): 7 tests covering < 1ms classification and token-free routing.
  - LangGraph 8-node Lifecycle & Structured Tools: 176 integration and unit tests.

---

## 11. Production Deployment Checklist

1. **Container Security**: Runs under dedicated non-root user `appuser` (UID 10001).
2. **Database Pooling**: Supabase connection recycling (`pool_recycle=1800`) and liveness checks (`pool_pre_ping=True`) active.
3. **Stateless Microservice**: No Kafka dependencies, no in-memory state, fully horizontally scalable behind any load balancer.
4. **Resilient AI Pipeline**: Deterministic fallbacks ensure 100% API availability even if the external LLM is cold or unreachable.
