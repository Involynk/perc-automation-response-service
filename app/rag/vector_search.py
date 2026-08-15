from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.agent import RetrievedDocument


class VectorSearch:
    """
    PostgreSQL pgvector dense similarity search engine.
    Queries resp_knowledge_chunks using cosine distance (<=> operator) against HNSW index.
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        min_similarity: float = 0.70,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """
        Executes vector similarity search using cosine similarity = 1.0 - cosine_distance.
        Enforces top_k clamping (1 to 5) and strict branch/course isolation rules.
        """
        # Clamp top_k between 1 and 5
        top_k = max(1, min(5, top_k))

        # Vector dimension check
        if len(query_vector) != 384:
            raise ValueError(f"Expected 384-dimensional query vector, got {len(query_vector)}")

        vec_str = "[" + ",".join(str(f) for f in query_vector) + "]"

        # Build parameterized SQL query with cosine similarity
        where_clauses = [
            "embedding IS NOT NULL",
            "(1.0 - (embedding <=> CAST(:query_vector AS vector))) >= :min_similarity",
        ]
        params: Dict[str, Any] = {
            "query_vector": vec_str,
            "min_similarity": float(min_similarity),
            "top_k": top_k,
        }

        if category:
            where_clauses.append("category = :category")
            params["category"] = category

        if document_type:
            where_clauses.append("document_type = :document_type")
            params["document_type"] = document_type

        if source_priority:
            where_clauses.append("source_priority = :source_priority")
            params["source_priority"] = source_priority

        # Branch isolation rule: If branch_id supplied, match requested branch OR global (NULL)
        if branch_id:
            where_clauses.append("(branch_id IS NULL OR branch_id = :branch_id)")
            params["branch_id"] = branch_id

        # Course isolation rule: If course_id supplied, match requested course OR global (NULL)
        if course_id:
            where_clauses.append("(course_id IS NULL OR course_id = :course_id)")
            params["course_id"] = course_id

        query_sql = f"""
            SELECT
                id,
                document_id,
                source_file,
                category,
                document_type,
                section,
                heading,
                chunk_index,
                chunk_content,
                token_count,
                source_priority,
                course_id,
                branch_id,
                target_class,
                metadata_payload,
                (1.0 - (embedding <=> CAST(:query_vector AS vector))) AS similarity_score
            FROM resp_knowledge_chunks
            WHERE {" AND ".join(where_clauses)}
            ORDER BY embedding <=> CAST(:query_vector AS vector) ASC
            LIMIT :top_k;
        """

        rows = self.db.execute(text(query_sql), params).fetchall()

        results: List[RetrievedDocument] = []
        for r in rows:
            similarity = float(r.similarity_score)
            # Clamp similarity between 0.0 and 1.0 for RetrievedDocument schema validation
            clamped_score = max(0.0, min(1.0, round(similarity, 4)))

            meta = dict(r.metadata_payload) if isinstance(r.metadata_payload, dict) else {}
            meta.update({
                "category": r.category,
                "document_type": r.document_type,
                "section": r.section,
                "heading": r.heading,
                "chunk_index": r.chunk_index,
                "token_count": r.token_count,
                "source_priority": r.source_priority,
                "course_id": r.course_id,
                "branch_id": r.branch_id,
                "target_class": r.target_class,
                "search_mode": "vector",
                "cosine_similarity": clamped_score,
            })

            results.append(
                RetrievedDocument(
                    doc_id=r.document_id,
                    chunk_id=r.id,
                    source_file=r.source_file,
                    content=r.chunk_content,
                    relevance_score=clamped_score,
                    metadata=meta,
                )
            )

        return results
