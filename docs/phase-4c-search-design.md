# Phase 4C — RAG Retrieval Architecture & Search Design

---

## 1. Executive Summary

Phase 4C implements the dedicated knowledge retrieval engine for the PERC Response Service.

The retrieval layer bridges student queries to relevant unstructured knowledge chunks stored in PostgreSQL (`resp_knowledge_chunks`) without generating final natural-language answers or invoking downstream LLMs.

```
Student Query
     ↓
Query Embedding (all-MiniLM-L6-v2, 384-d)
     ↓
┌────────────────────────────────────────────────────────┐
│                   Hybrid Searcher                      │
│                                                        │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │     VectorSearch      │   │    KeywordSearch     │  │
│  │ (pgvector cosine <=>) │   │ (PostgreSQL FTS/Rnk) │  │
│  └───────────┬───────────┘   └───────────┬──────────┘  │
│              └─────────────┬─────────────┘             │
│                            ↓                           │
│              Reciprocal Rank Fusion (RRF)              │
│                 RRF(d) = Σ 1/(k + rank)                │
└────────────────────────────┬───────────────────────────┘
                             ↓
                 Filtered RetrievedDocument[]
```

---

## 2. Component Architecture

### 2.1 Query Embedding
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Output Dimension**: 384-dimensional unit-normalized float vector
- **Validation**: Strict pre-execution check (`len(query_vector) == 384`).
- **Determinism**: Production queries use `SentenceTransformerEmbeddingProvider`; unit tests support `DeterministicMockEmbeddingProvider`.

---

### 2.2 Dense Vector Search (`VectorSearch`)
- **Engine**: PostgreSQL `pgvector` extension with HNSW index (`resp_knowledge_chunks_embedding_hnsw_idx`).
- **Distance Metric**: Cosine distance (`<=>`).
- **Similarity Metric**:
  $$\text{Cosine Similarity} = 1.0 - (\text{embedding} \Leftrightarrow \text{query\_vector})$$
- **Filtering**:
  - Minimum similarity threshold: `min_similarity` (default `0.70`, configurable down to `0.40`).
  - Top K: Clamped strictly between `1` and `5` (default `3`).
- **Score Semantics**: `relevance_score` represents direct cosine similarity $\in [0.0, 1.0]$.

---

### 2.3 PostgreSQL Full-Text Keyword Search (`KeywordSearch`)
- **Engine**: Native PostgreSQL full-text search (`to_tsvector`, `to_tsquery`, `ts_rank_cd`).
- **Token Processing**: Alphanumeric extraction with standard English stopword filtering (prevents common stopwords from triggering broad false positives).
- **Ranking**:
  $$\text{Normalized FTS Score} = \frac{\text{ts\_rank\_cd}}{\text{ts\_rank\_cd} + 0.1}$$
- **Fallback**: Token-weighted `ILIKE` ranking if morphological dictionary yields zero lexemes.

---

### 2.4 Hybrid Search & Reciprocal Rank Fusion (`HybridSearch`)
Hybrid search merges dense semantic recall with precise lexical keyword matching using Reciprocal Rank Fusion (RRF):

$$RRF(d) = \sum_{m \in \{\text{dense}, \text{keyword}\}} \frac{I(d \in m)}{k_{\text{rrf}} + \text{rank}_m(d)}$$

- **Default Smoothing Constant ($k_{\text{rrf}}$)**: `60`
- **Normalization**: Normalized against the maximum theoretical RRF score ($2 / (k_{\text{rrf}} + 1)$):
  $$\text{Normalized RRF} = \frac{RRF(d)}{2 / (60 + 1)}$$
- **Candidate Pool**: Fetches top $2 \times \text{top\_k}$ (minimum 6) candidates from each modality before rank merging.

---

## 3. Metadata Filtering & Security Isolation Rules

All metadata filters are applied directly inside the SQL query:

| Filter | SQL Clause / Logic | Purpose |
|---|---|---|
| `category` | `category = :category` | Restricts search to single intent category |
| `document_type` | `document_type = :document_type` | Restricts search to catalog, policy, guide, etc. |
| `source_priority` | `source_priority = :source_priority` | `authoritative_rag` vs `secondary_rag` |
| **`branch_id`** | **`(branch_id IS NULL OR branch_id = :branch_id)`** | **Branch Isolation**: Preserves global knowledge while preventing cross-campus leakage |
| **`course_id`** | **`(course_id IS NULL OR course_id = :course_id)`** | **Course Isolation**: Preserves global knowledge while filtering specific course chunks |

---

## 4. No-Result & Negative Query Behavior

If no chunks satisfy the similarity threshold or keyword matches:
- The retriever returns an empty list: `[]`.
- **Strict Invariants**:
  - No LLM invocation or hallucinated fallback.
  - No automatic lowering of similarity thresholds.
  - No unrelated or out-of-scope chunks returned.

---

## 5. RetrievedDocument Contract (`app.schemas.agent.RetrievedDocument`)

Every search result strictly conforms to `RetrievedDocument`:

```json
{
  "doc_id": "required-documents",
  "chunk_id": "required-documents_chk_001_8ab2c3d4e5",
  "source_file": "required-documents.md",
  "content": "# Required Documents for PERC Admission > ## Commonly Required Documents\n...",
  "relevance_score": 0.9761,
  "metadata": {
    "category": "C7_REQUIRED_DOCUMENTS",
    "document_type": "guide",
    "section": "Commonly Required Documents",
    "heading": "Commonly Required Documents",
    "chunk_index": 1,
    "token_count": 92,
    "source_priority": "authoritative_rag",
    "course_id": null,
    "branch_id": null,
    "search_mode": "hybrid",
    "rrf_raw_score": 0.032014,
    "rrf_normalized_score": 0.9761,
    "vector_rank": 1,
    "keyword_rank": 1
  }
}
```

---

## 6. Limitations & Boundaries

1. **Pure Retrieval**: Phase 4C does not generate natural language responses.
2. **Dataset Scale**: Designed and verified for the 104 knowledge chunks in `resp_knowledge_chunks`.
3. **No External Dependencies**: Operates entirely within PostgreSQL + pgvector + SentenceTransformer.
