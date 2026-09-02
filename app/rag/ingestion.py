import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.knowledge_chunk import KnowledgeChunkModel
from app.rag.chunker import SemanticMarkdownChunker
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.loader import DocumentLoader, LoadedDocument
from app.rag.metadata import EnrichedChunk, MetadataEnricher

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    """Summary metrics produced after knowledge ingestion execution."""
    total_files_discovered: int
    eligible_files_processed: int
    tier_3_files_skipped: int
    total_chunks_created: int
    total_tokens_estimated: int
    vector_dimension: int
    upserted_count: int


class KnowledgeIngestionPipeline:
    """
    Orchestrates end-to-end knowledge ingestion:
    Document Loading -> Semantic Chunking -> Metadata Enrichment -> Embedding Generation -> DB Upsert.
    """
    def __init__(
        self,
        unstructured_dir: Path,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunker: Optional[SemanticMarkdownChunker] = None,
        enricher: Optional[MetadataEnricher] = None,
    ):
        self.unstructured_dir = Path(unstructured_dir)
        self.loader = DocumentLoader(self.unstructured_dir)
        self.chunker = chunker or SemanticMarkdownChunker()
        self.enricher = enricher or MetadataEnricher()
        self.embedding_provider = embedding_provider or get_embedding_provider("mock")

    def process_all_documents(self) -> List[EnrichedChunk]:
        """
        Loads, chunks, enriches, and returns all eligible knowledge chunks.
        Strictly excludes Tier 3 files.
        """
        eligible_docs = self.loader.discover_eligible_documents(include_tier_3=False)
        all_enriched_chunks: List[EnrichedChunk] = []

        for doc in eligible_docs:
            raw_chunks = self.chunker.chunk_document(doc)
            for raw_chunk in raw_chunks:
                enriched = self.enricher.enrich_chunk(raw_chunk)
                all_enriched_chunks.append(enriched)

        return all_enriched_chunks

    def process_loaded_document(self, document: LoadedDocument) -> List[EnrichedChunk]:
        """Chunk and enrich a single already-loaded document."""
        raw_chunks = self.chunker.chunk_document(document)
        return [self.enricher.enrich_chunk(raw_chunk) for raw_chunk in raw_chunks]

    def _upsert_chunks(self, db: Session, enriched_chunks: List[EnrichedChunk]) -> int:
        import json
        from sqlalchemy import text

        upsert_query = text("""
            INSERT INTO resp_knowledge_chunks (
                id, document_id, source_file, category, document_type, section, heading,
                chunk_index, chunk_content, token_count, source_priority, course_id, branch_id,
                target_class, metadata_payload, embedding, updated_at
            ) VALUES (
                :id, :document_id, :source_file, :category, :document_type, :section, :heading,
                :chunk_index, :chunk_content, :token_count, :source_priority, :course_id, :branch_id,
                :target_class, CAST(:metadata_payload AS jsonb), CAST(:embedding AS vector), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                source_file = EXCLUDED.source_file,
                category = EXCLUDED.category,
                document_type = EXCLUDED.document_type,
                section = EXCLUDED.section,
                heading = EXCLUDED.heading,
                chunk_index = EXCLUDED.chunk_index,
                chunk_content = EXCLUDED.chunk_content,
                token_count = EXCLUDED.token_count,
                source_priority = EXCLUDED.source_priority,
                course_id = EXCLUDED.course_id,
                branch_id = EXCLUDED.branch_id,
                target_class = EXCLUDED.target_class,
                metadata_payload = EXCLUDED.metadata_payload,
                embedding = EXCLUDED.embedding,
                updated_at = NOW();
        """)

        upserted_count = 0
        for chunk in enriched_chunks:
            embedding_vec = self.embedding_provider.embed_text(chunk.content)
            vec_str = "[" + ",".join(str(f) for f in embedding_vec) + "]"
            db.execute(
                upsert_query,
                {
                    "id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "source_file": chunk.source_file,
                    "category": chunk.category,
                    "document_type": chunk.document_type,
                    "section": chunk.section,
                    "heading": chunk.heading,
                    "chunk_index": chunk.chunk_index,
                    "chunk_content": chunk.content,
                    "token_count": chunk.token_count,
                    "source_priority": chunk.source_priority,
                    "course_id": chunk.course_id,
                    "branch_id": chunk.branch_id,
                    "target_class": chunk.target_class,
                    "metadata_payload": json.dumps(chunk.metadata_payload),
                    "embedding": vec_str,
                },
            )
            upserted_count += 1
        return upserted_count

    def replace_document_in_store(
        self,
        db: Session,
        document: LoadedDocument,
        dry_run: bool = False,
    ) -> tuple[List[EnrichedChunk], int]:
        """
        Re-index one document: delete previous chunks for document_id, then insert new embeddings.
        The live RAG retriever reads from resp_knowledge_chunks, so no service redeploy is required.
        """
        from sqlalchemy import text

        enriched_chunks = self.process_loaded_document(document)
        if dry_run:
            return enriched_chunks, len(enriched_chunks)

        db.execute(
            text("DELETE FROM resp_knowledge_chunks WHERE document_id = :document_id"),
            {"document_id": document.document_id},
        )
        upserted = self._upsert_chunks(db, enriched_chunks)
        return enriched_chunks, upserted

    def delete_document_from_store(self, db: Session, document_id: str) -> int:
        from sqlalchemy import text

        result = db.execute(
            text("DELETE FROM resp_knowledge_chunks WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        return int(result.rowcount or 0)

    def run_ingestion(self, db: Optional[Session] = None, dry_run: bool = False) -> IngestionSummary:
        """
        Executes knowledge ingestion pipeline.
        If dry_run is True or db is None, skips database writes and returns computed metrics.
        """
        all_docs = self.loader.discover_eligible_documents(include_tier_3=True)
        tier_3_count = sum(1 for d in all_docs if d.tier == 3)
        eligible_docs = [d for d in all_docs if d.tier != 3]

        enriched_chunks = self.process_all_documents()
        total_tokens = sum(c.token_count for c in enriched_chunks)
        dim = self.embedding_provider.dimension

        upserted_count = 0

        if db is not None and not dry_run:
            upserted_count = self._upsert_chunks(db, enriched_chunks)
            db.commit()

        return IngestionSummary(
            total_files_discovered=len(all_docs),
            eligible_files_processed=len(eligible_docs),
            tier_3_files_skipped=tier_3_count,
            total_chunks_created=len(enriched_chunks),
            total_tokens_estimated=total_tokens,
            vector_dimension=dim,
            upserted_count=upserted_count if not dry_run else len(enriched_chunks),
        )
