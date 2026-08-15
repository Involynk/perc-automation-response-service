import re
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.agent import RetrievedDocument


STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
}


class KeywordSearch:
    """
    PostgreSQL-native full-text and keyword search engine.
    Uses PostgreSQL text search vectors (to_tsvector / plainto_tsquery) and ts_rank
    with ILIKE token fallback without external search engines.
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query_text: str,
        top_k: int = 3,
        min_score: float = 0.0,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """
        Executes PostgreSQL native full-text keyword search.
        Enforces top_k clamping (1 to 5) and strict branch/course isolation rules.
        """
        if not query_text or not query_text.strip():
            return []

        top_k = max(1, min(5, top_k))
        cleaned_query = query_text.strip()

        # Build base filter clauses
        where_clauses = []
        params: Dict[str, Any] = {
            "query_text": cleaned_query,
            "min_score": float(min_score),
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

        # Branch isolation rule
        if branch_id:
            where_clauses.append("(branch_id IS NULL OR branch_id = :branch_id)")
            params["branch_id"] = branch_id

        # Course isolation rule
        if course_id:
            where_clauses.append("(course_id IS NULL OR course_id = :course_id)")
            params["course_id"] = course_id

        where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

        # Clean alphanumeric meaningful tokens from query (exclude common stop words)
        raw_tokens = re.findall(r"[a-zA-Z0-9]+", cleaned_query.lower())
        tokens = [t for t in raw_tokens if len(t) > 2 and t not in STOP_WORDS]
        if not tokens:
            tokens = [t for t in raw_tokens if len(t) > 1]
            if not tokens:
                return []

        # Build tsquery expressions
        or_tsquery_terms = " | ".join(tokens)

        # Primary Full-Text Search Query combining websearch and term disjunction
        fts_query = f"""
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
                ts_rank_cd(
                    to_tsvector('english', chunk_content),
                    to_tsquery('english', :or_tsquery)
                ) AS fts_rank
            FROM resp_knowledge_chunks
            WHERE to_tsvector('english', chunk_content) @@ to_tsquery('english', :or_tsquery)
            {where_sql}
            ORDER BY fts_rank DESC
            LIMIT :top_k;
        """
        params["or_tsquery"] = or_tsquery_terms

        try:
            rows = self.db.execute(text(fts_query), params).fetchall()
        except Exception:
            rows = []

        # Fallback to token-weighted ILIKE matching if full-text query returned no rows
        if not rows and tokens:
            like_clauses = []
            score_terms = []
            for idx, tok in enumerate(tokens[:5]):
                param_name = f"tok_{idx}"
                like_clauses.append(f"chunk_content ILIKE :{param_name}")
                score_terms.append(f"(CASE WHEN chunk_content ILIKE :{param_name} THEN 1 ELSE 0 END)")
                params[param_name] = f"%{tok}%"

            ilike_where = " OR ".join(like_clauses)
            ilike_score = " + ".join(score_terms)
            ilike_query = f"""
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
                    ({ilike_score}) * 0.1 AS fts_rank
                FROM resp_knowledge_chunks
                WHERE ({ilike_where})
                {where_sql}
                ORDER BY fts_rank DESC
                LIMIT :top_k;
            """
            rows = self.db.execute(text(ilike_query), params).fetchall()

        results: List[RetrievedDocument] = []
        for r in rows:
            raw_rank = float(r.fts_rank)
            # Normalize rank to [0.0, 1.0] using hyperbolic scaling: score = rank / (rank + 0.1)
            # ensures relevant keyword hits yield scores in 0.5 - 0.95 range
            norm_score = raw_rank / (raw_rank + 0.1) if raw_rank > 0 else 0.1
            clamped_score = max(0.0, min(1.0, round(norm_score, 4)))

            if clamped_score < min_score:
                continue

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
                "search_mode": "keyword",
                "raw_fts_rank": raw_rank,
                "keyword_score": clamped_score,
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
