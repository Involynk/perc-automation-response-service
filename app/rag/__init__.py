"""
RAG (Retrieval-Augmented Generation) Knowledge Module for PERC Response Service.
"""

from app.rag.chunker import RawChunk, SemanticMarkdownChunker
from app.rag.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
)
from app.rag.hybrid_search import HybridSearch
from app.rag.ingestion import IngestionSummary, KnowledgeIngestionPipeline
from app.rag.keyword_search import KeywordSearch
from app.rag.loader import DocumentLoader, LoadedDocument
from app.rag.metadata import EnrichedChunk, MetadataEnricher
from app.rag.retrieval import KnowledgeRetriever
from app.rag.vector_search import VectorSearch

__all__ = [
    "LoadedDocument",
    "DocumentLoader",
    "RawChunk",
    "SemanticMarkdownChunker",
    "EnrichedChunk",
    "MetadataEnricher",
    "EmbeddingProvider",
    "DeterministicMockEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "get_embedding_provider",
    "IngestionSummary",
    "KnowledgeIngestionPipeline",
    "VectorSearch",
    "KeywordSearch",
    "HybridSearch",
    "KnowledgeRetriever",
]
