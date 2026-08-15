from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.rag.keyword_search import KeywordSearch
from app.rag.vector_search import VectorSearch
from app.schemas.agent import RetrievedDocument


class HybridSearch:
    """
    Hybrid Search engine combining Dense Vector Search and PostgreSQL Keyword Search
    using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, db: Session, rrf_k: int = 60):
        self.db = db
        self.rrf_k = rrf_k
        self.vector_search = VectorSearch(db)
        self.keyword_search = KeywordSearch(db)

    def search(
        self,
        query_text: str,
        query_vector: List[float],
        top_k: int = 3,
        min_similarity: float = 0.70,
        rrf_k: Optional[int] = None,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """
        Executes hybrid retrieval:
        1. Dense Vector Search (pgvector cosine similarity)
        2. Full-text Keyword Search (PostgreSQL FTS)
        3. Reciprocal Rank Fusion (RRF) combination:
           RRF(d) = sum(1 / (k + rank_i))
        """
        top_k = max(1, min(5, top_k))
        active_rrf_k = rrf_k if rrf_k is not None else self.rrf_k
        candidate_k = max(top_k * 2, 6)

        # 1. Fetch dense vector candidates
        vector_results = self.vector_search.search(
            query_vector=query_vector,
            top_k=candidate_k,
            min_similarity=min_similarity,
            category=category,
            course_id=course_id,
            branch_id=branch_id,
            document_type=document_type,
            source_priority=source_priority,
        )

        # 2. Fetch keyword search candidates
        keyword_results = self.keyword_search.search(
            query_text=query_text,
            top_k=candidate_k,
            min_score=0.0,
            category=category,
            course_id=course_id,
            branch_id=branch_id,
            document_type=document_type,
            source_priority=source_priority,
        )

        # If both empty, return empty list
        if not vector_results and not keyword_results:
            return []

        # 3. Reciprocal Rank Fusion Map
        # Key: chunk_id -> (RetrievedDocument, vector_rank, keyword_rank, rrf_score)
        doc_map: Dict[str, RetrievedDocument] = {}
        vector_rank_map: Dict[str, int] = {}
        keyword_rank_map: Dict[str, int] = {}
        rrf_scores: Dict[str, float] = {}

        for rank, doc in enumerate(vector_results, start=1):
            chunk_id = doc.chunk_id or doc.source_file
            doc_map[chunk_id] = doc
            vector_rank_map[chunk_id] = rank
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (active_rrf_k + rank))

        for rank, doc in enumerate(keyword_results, start=1):
            chunk_id = doc.chunk_id or doc.source_file
            if chunk_id not in doc_map:
                doc_map[chunk_id] = doc
            keyword_rank_map[chunk_id] = rank
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (active_rrf_k + rank))

        # Max theoretical score for rank 1 in both modalities
        max_possible_rrf = 2.0 / (active_rrf_k + 1.0)

        # Sort candidates by raw RRF score descending
        sorted_chunks = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

        results: List[RetrievedDocument] = []
        for chunk_id, raw_rrf in sorted_chunks[:top_k]:
            doc = doc_map[chunk_id]
            norm_score = raw_rrf / max_possible_rrf
            clamped_score = max(0.0, min(1.0, round(norm_score, 4)))

            meta = dict(doc.metadata)
            meta.update({
                "search_mode": "hybrid",
                "rrf_raw_score": round(raw_rrf, 6),
                "rrf_normalized_score": clamped_score,
                "vector_rank": vector_rank_map.get(chunk_id),
                "keyword_rank": keyword_rank_map.get(chunk_id),
            })

            results.append(
                RetrievedDocument(
                    doc_id=doc.doc_id,
                    chunk_id=doc.chunk_id,
                    source_file=doc.source_file,
                    content=doc.content,
                    relevance_score=clamped_score,
                    metadata=meta,
                )
            )

        return results
