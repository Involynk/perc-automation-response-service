from typing import List, Optional
from sqlalchemy.orm import Session

from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.hybrid_search import HybridSearch
from app.rag.keyword_search import KeywordSearch
from app.rag.vector_search import VectorSearch
from app.schemas.agent import RetrievedDocument


class KnowledgeRetriever:
    """
    High-level unified knowledge retrieval facade for the PERC Response Service.
    Coordinates query embedding, vector search, keyword search, hybrid RRF fusion,
    and metadata filtering.
    """

    def __init__(
        self,
        db: Session,
        embedding_provider: Optional[EmbeddingProvider] = None,
        default_top_k: int = 3,
        default_min_similarity: float = 0.70,
        default_rrf_k: int = 60,
    ):
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider("sentence-transformers")
        self.default_top_k = default_top_k
        self.default_min_similarity = default_min_similarity
        self.default_rrf_k = default_rrf_k

        self.vector_engine = VectorSearch(db)
        self.keyword_engine = KeywordSearch(db)
        self.hybrid_engine = HybridSearch(db, rrf_k=default_rrf_k)

    def _embed_query(self, query: str) -> List[float]:
        """Embeds and validates the query vector."""
        vec = self.embedding_provider.embed_text(query)
        if len(vec) != 384:
            raise ValueError(
                f"Invalid query embedding dimension {len(vec)}; expected 384 dimensions."
            )
        return vec

    def search_vector(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """Executes pure dense vector similarity search."""
        if not query or not query.strip():
            return []

        top_k = top_k if top_k is not None else self.default_top_k
        min_sim = min_similarity if min_similarity is not None else self.default_min_similarity

        query_vec = self._embed_query(query.strip())
        return self.vector_engine.search(
            query_vector=query_vec,
            top_k=top_k,
            min_similarity=min_sim,
            category=category,
            course_id=course_id,
            branch_id=branch_id,
            document_type=document_type,
            source_priority=source_priority,
        )

    def search_keyword(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: float = 0.0,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """Executes pure PostgreSQL full-text keyword search."""
        if not query or not query.strip():
            return []

        top_k = top_k if top_k is not None else self.default_top_k
        return self.keyword_engine.search(
            query_text=query.strip(),
            top_k=top_k,
            min_score=min_score,
            category=category,
            course_id=course_id,
            branch_id=branch_id,
            document_type=document_type,
            source_priority=source_priority,
        )

    def search_hybrid(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        rrf_k: Optional[int] = None,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """Executes hybrid dense + keyword search with Reciprocal Rank Fusion."""
        if not query or not query.strip():
            return []

        top_k = top_k if top_k is not None else self.default_top_k
        min_sim = min_similarity if min_similarity is not None else self.default_min_similarity
        active_rrf_k = rrf_k if rrf_k is not None else self.default_rrf_k

        query_vec = self._embed_query(query.strip())
        return self.hybrid_engine.search(
            query_text=query.strip(),
            query_vector=query_vec,
            top_k=top_k,
            min_similarity=min_sim,
            rrf_k=active_rrf_k,
            category=category,
            course_id=course_id,
            branch_id=branch_id,
            document_type=document_type,
            source_priority=source_priority,
        )

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        category: Optional[str] = None,
        course_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        document_type: Optional[str] = None,
        source_priority: Optional[str] = None,
    ) -> List[RetrievedDocument]:
        """
        Public high-level search method supporting 'hybrid', 'vector', and 'keyword' modes.
        """
        mode_lower = (mode or "hybrid").lower()
        if mode_lower == "vector":
            return self.search_vector(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                category=category,
                course_id=course_id,
                branch_id=branch_id,
                document_type=document_type,
                source_priority=source_priority,
            )
        elif mode_lower == "keyword":
            return self.search_keyword(
                query=query,
                top_k=top_k,
                category=category,
                course_id=course_id,
                branch_id=branch_id,
                document_type=document_type,
                source_priority=source_priority,
            )
        elif mode_lower == "hybrid":
            return self.search_hybrid(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                category=category,
                course_id=course_id,
                branch_id=branch_id,
                document_type=document_type,
                source_priority=source_priority,
            )
        else:
            raise ValueError(f"Unsupported search mode '{mode}'. Use 'hybrid', 'vector', or 'keyword'.")
