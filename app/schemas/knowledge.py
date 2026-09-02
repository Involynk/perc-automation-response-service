from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeDocumentSummary(BaseModel):
    id: str
    filename: str
    title: str
    content_type: str
    category: Optional[str] = None
    chunk_count: int
    token_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentDetail(KnowledgeDocumentSummary):
    raw_content: str


class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    raw_content: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, max_length=50)


class KnowledgeChunkView(BaseModel):
    id: str
    section: str
    heading: str
    chunk_index: int
    token_count: int
    category: str
    chunk_content: str


class KnowledgeIngestResponse(BaseModel):
    document: KnowledgeDocumentDetail
    chunks_indexed: int
    vector_dimension: int
    message: str


class KnowledgeListResponse(BaseModel):
    documents: List[KnowledgeDocumentSummary]
    total: int
    total_chunks: int
