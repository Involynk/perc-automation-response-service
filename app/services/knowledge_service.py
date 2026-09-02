import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.knowledge_chunk import KnowledgeChunkModel
from app.db.models.knowledge_document import KnowledgeDocumentModel
from app.rag.embeddings import get_embedding_provider
from app.rag.extractors import extract_text
from app.rag.ingestion import KnowledgeIngestionPipeline
from app.rag.loader import LoadedDocument
from app.schemas.knowledge import (
    KnowledgeChunkView,
    KnowledgeDocumentDetail,
    KnowledgeDocumentSummary,
    KnowledgeDocumentUpdate,
)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def slugify_document_id(filename: str) -> str:
    stem = Path(filename).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return (slug or "document")[:80]


def title_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("-", " ").replace("_", " ").strip().title()


class KnowledgeBaseService:
    """Persists uploaded knowledge documents and re-indexes RAG embeddings in PostgreSQL."""

    def __init__(self, db: Session, pipeline: Optional[KnowledgeIngestionPipeline] = None):
        self.db = db
        self.pipeline = pipeline or KnowledgeIngestionPipeline(
            unstructured_dir=Path("MockData/unstructured"),
            embedding_provider=get_embedding_provider(),
        )

    def list_documents(self, query: Optional[str] = None) -> Tuple[List[KnowledgeDocumentModel], int]:
        q = self.db.query(KnowledgeDocumentModel)
        if query:
            like = f"%{query.strip()}%"
            q = q.filter(
                (KnowledgeDocumentModel.title.ilike(like))
                | (KnowledgeDocumentModel.filename.ilike(like))
                | (KnowledgeDocumentModel.id.ilike(like))
            )
        documents = q.order_by(KnowledgeDocumentModel.updated_at.desc()).all()
        total_chunks = self.db.query(func.coalesce(func.sum(KnowledgeDocumentModel.chunk_count), 0)).scalar()
        return documents, int(total_chunks or 0)

    def get_document(self, document_id: str) -> KnowledgeDocumentModel:
        document = self.db.query(KnowledgeDocumentModel).filter(KnowledgeDocumentModel.id == document_id).first()
        if document is None:
            raise KeyError(document_id)
        return document

    def list_chunks(self, document_id: str) -> List[KnowledgeChunkModel]:
        self.get_document(document_id)
        return (
            self.db.query(KnowledgeChunkModel)
            .filter(KnowledgeChunkModel.document_id == document_id)
            .order_by(KnowledgeChunkModel.chunk_index.asc())
            .all()
        )

    def ingest_upload(
        self,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
        title: Optional[str] = None,
        document_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[KnowledgeDocumentModel, int]:
        if not filename:
            raise ValueError("A filename is required.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("File exceeds the 10 MB upload limit.")

        extracted = extract_text(filename, data, content_type)
        resolved_id = document_id.strip() if document_id and document_id.strip() else slugify_document_id(filename)
        resolved_title = (title or "").strip() or title_from_filename(filename)
        return self._index_content(
            document_id=resolved_id,
            filename=filename,
            title=resolved_title,
            content_type=extracted.content_type,
            raw_content=extracted.text,
            category=category,
        )

    def update_document(self, document_id: str, payload: KnowledgeDocumentUpdate) -> Tuple[KnowledgeDocumentModel, int]:
        document = self.get_document(document_id)
        title = payload.title.strip() if payload.title else document.title
        raw_content = payload.raw_content if payload.raw_content is not None else document.raw_content
        category = payload.category if payload.category is not None else document.category
        return self._index_content(
            document_id=document.id,
            filename=document.filename,
            title=title,
            content_type=document.content_type,
            raw_content=raw_content,
            category=category,
        )

    def reindex_document(self, document_id: str) -> Tuple[KnowledgeDocumentModel, int]:
        document = self.get_document(document_id)
        return self._index_content(
            document_id=document.id,
            filename=document.filename,
            title=document.title,
            content_type=document.content_type,
            raw_content=document.raw_content,
            category=document.category,
        )

    def delete_document(self, document_id: str) -> None:
        document = self.get_document(document_id)
        self.pipeline.delete_document_from_store(self.db, document.id)
        self.db.delete(document)
        self.db.commit()

    def _index_content(
        self,
        document_id: str,
        filename: str,
        title: str,
        content_type: str,
        raw_content: str,
        category: Optional[str],
    ) -> Tuple[KnowledgeDocumentModel, int]:
        if not raw_content or not raw_content.strip():
            raise ValueError("Document content is empty.")

        now = datetime.now(timezone.utc)
        document = self.db.query(KnowledgeDocumentModel).filter(KnowledgeDocumentModel.id == document_id).first()
        if document is None:
            document = KnowledgeDocumentModel(
                id=document_id,
                filename=filename[:255],
                title=title[:255],
                content_type=content_type,
                raw_content=raw_content,
                category=category,
                status="processing",
                created_at=now,
                updated_at=now,
            )
            self.db.add(document)
        else:
            document.filename = filename[:255]
            document.title = title[:255]
            document.content_type = content_type
            document.raw_content = raw_content
            document.category = category
            document.status = "processing"
            document.error_message = None
            document.updated_at = now
        self.db.commit()

        loaded = LoadedDocument(
            document_id=document_id,
            filename=filename,
            file_path=Path(filename),
            raw_content=raw_content,
            tier=2,
        )

        try:
            chunks, upserted = self.pipeline.replace_document_in_store(self.db, loaded, dry_run=False)
            document.chunk_count = upserted
            document.token_count = sum(chunk.token_count for chunk in chunks)
            document.status = "indexed"
            document.error_message = None
            document.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(document)
            return document, upserted
        except Exception as exc:
            self.db.rollback()
            document = self.db.query(KnowledgeDocumentModel).filter(KnowledgeDocumentModel.id == document_id).first()
            if document is not None:
                document.status = "failed"
                document.error_message = str(exc)
                document.updated_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    @staticmethod
    def to_summary(document: KnowledgeDocumentModel) -> KnowledgeDocumentSummary:
        return KnowledgeDocumentSummary.model_validate(document, from_attributes=True)

    @staticmethod
    def to_detail(document: KnowledgeDocumentModel) -> KnowledgeDocumentDetail:
        return KnowledgeDocumentDetail.model_validate(document, from_attributes=True)

    @staticmethod
    def to_chunk_view(chunk: KnowledgeChunkModel) -> KnowledgeChunkView:
        return KnowledgeChunkView(
            id=chunk.id,
            section=chunk.section,
            heading=chunk.heading,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            category=chunk.category,
            chunk_content=chunk.chunk_content,
        )
