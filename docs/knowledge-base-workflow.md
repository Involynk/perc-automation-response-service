# Knowledge base RAG workflow

How a document goes from upload to a live chatbot answer, and back again when it's edited.

## 1. Two knowledge sources

The response service pulls facts from two places:

- **Structured data** — Postgres tables for courses, fees, eligibility, availability. Queried directly, no embeddings involved.
- **Unstructured knowledge** — policy text, hostel rules, FAQs. This is what the knowledge base UI manages. It's embedded and searched by meaning, not exact keywords.

This doc covers the unstructured path only.

## 2. Storage: two tables

| Table | Holds | Written by |
|---|---|---|
| `resp_knowledge_documents` | One row per source document: id, title, filename, raw markdown, category, status, chunk/token counts | `KnowledgeBaseService` |
| `resp_knowledge_chunks` | One row per chunk: text, section/heading, category, course/branch tags, and a `vector` embedding column (pgvector) | `KnowledgeIngestionPipeline` |

The live retriever only ever reads `resp_knowledge_chunks`. Editing a document rewrites its chunk rows in place, so the next question asked immediately sees the new content. No redeploy, no cache to bust.

## 3. Ingestion pipeline (upload → searchable chunks)

```
Upload file (.md/.txt/.pdf/.docx/.html/.csv)
        │
        ▼
1. Extract text  →  app/rag/extractors.py
   - .md/.txt/.html/.csv: decoded and (for html) tag-stripped
   - .pdf: pypdf reads each page, wraps as "## Page N" markdown
   - .docx: python-docx walks paragraphs, maps Heading 1/2/3 styles to # / ## / ###
        │
        ▼
2. Chunk  →  app/rag/chunker.py (SemanticMarkdownChunker)
   - Splits along H2/H3 markdown headers, not fixed character windows
   - Keeps tables and lists intact inside a chunk
   - Targets ~100-450 tokens per chunk (word count × 1.3, heuristic)
   - Each chunk gets a stable id: {doc_id}_chk_{index}_{content_hash}
        │
        ▼
3. Enrich  →  app/rag/metadata.py (MetadataEnricher)
   - Tags each chunk with category, document_type, course/branch ids where inferable
        │
        ▼
4. Embed  →  app/rag/embeddings.py
   - Each chunk's text → a 384-dim float vector
   - Provider is swappable (see §5)
        │
        ▼
5. Upsert  →  app/rag/ingestion.py (KnowledgeIngestionPipeline)
   - DELETE all existing chunks for this document_id
   - INSERT new chunks with embeddings (ON CONFLICT DO UPDATE)
   - Does NOT commit — the caller (KnowledgeBaseService) owns the transaction
        │
        ▼
6. Service commits  →  app/services/knowledge_service.py
   - Writes the document row (status: processing → indexed) and the chunk
     upsert in a single flow; on failure, status flips to "failed" with
     the error message, and nothing is left half-written
```

Re-editing a document (via the UI's "Save & re-embed") or hitting "Reindex" replays steps 2-6 against the stored `raw_content` — no re-upload needed.

## 4. Retrieval pipeline (question → answer)

```
User question
        │
        ▼
Embed the query with the same provider used at ingestion
        │
        ▼
KnowledgeRetriever (app/rag/retrieval.py) runs hybrid search:
   ┌─────────────────────────┐   ┌──────────────────────────┐
   │ Vector search            │   │ Keyword search             │
   │ pgvector cosine similarity│   │ Postgres full-text search  │
   │ vector_search.py          │   │ keyword_search.py          │
   └─────────────┬────────────┘   └─────────────┬──────────────┘
                 └──────────────┬──────────────┘
                                ▼
                  Reciprocal Rank Fusion (RRF)
                  score(d) = Σ 1 / (k + rank_i)
                  hybrid_search.py combines both rankings
                                │
                                ▼
                  Filtered by category / course / branch,
                  clamped to top_k (max 5), min similarity 0.70
                                │
                                ▼
                  Top chunks passed to the LLM as context
                                │
                                ▼
                          Answer + sources
```

Vector search alone catches paraphrased questions ("what do I need to get in?" ≈ "admission requirements"). Keyword search alone catches exact terms embeddings can blur (course codes, dates). RRF fusion gets both without needing to pick one.

## 5. Embedding provider

`get_embedding_provider()` in `app/rag/embeddings.py` picks between two:

- **`DeterministicMockEmbeddingProvider`** (default) — hashes tokens into a 384-dim vector deterministically. No model download, near-zero memory. This is what runs in production today, specifically to avoid OOM kills on Render's 512MB instances.
- **`SentenceTransformerEmbeddingProvider`** — real semantic embeddings via `all-MiniLM-L6-v2`. Opt in with `EMBEDDING_PROVIDER=sentence-transformers`. Falls back to the mock provider automatically if the model can't load.

Whichever provider ingested a document must also serve queries against it — mixing the two means comparing vectors from different spaces, which silently degrades relevance instead of erroring.

## 6. What the UI adds on top

Everything above already existed as an ingestion pipeline (run at deploy time from `MockData/unstructured`). The knowledge base UI (`/knowledge`) exposes steps 1–6 as an on-demand API instead of a startup script:

| Action | Endpoint | Effect |
|---|---|---|
| Upload | `POST /api/v1/knowledge/documents` | Runs the full pipeline once, creates the document + chunk rows |
| Edit text | `PUT /api/v1/knowledge/documents/{id}` | Re-runs chunk → embed → upsert against the edited text |
| Reindex | `POST /api/v1/knowledge/documents/{id}/reindex` | Re-runs the pipeline against the stored text unchanged (useful after an embedding provider change) |
| Delete | `DELETE /api/v1/knowledge/documents/{id}` | Removes the document row and its chunks |
| Test retrieval | `POST /api/v1/response` (from the UI's "test retrieval" box) | Runs the real retrieval pipeline so you can confirm an edit changed the answer |

All endpoints sit behind `verify_internal_api_key` — the same header-based auth already used elsewhere in the service.

## 7. Failure handling

If chunking, embedding, or the DB upsert throws partway through step 5, `knowledge_service.py` rolls back and marks the document `status = failed` with the exception message stored on the row — the previous good chunks for that document are gone (step 5 deletes before inserting), so a failed re-embed leaves the document unsearchable until fixed and retried, not silently serving stale content.
