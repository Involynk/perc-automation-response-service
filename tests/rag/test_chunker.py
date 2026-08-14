from pathlib import Path
import pytest
from app.rag.chunker import SemanticMarkdownChunker
from app.rag.loader import DocumentLoader


@pytest.fixture
def chunker() -> SemanticMarkdownChunker:
    return SemanticMarkdownChunker()


def test_chunking_course_details(chunker: SemanticMarkdownChunker):
    loader = DocumentLoader(Path("MockData/unstructured"))
    doc = loader.load_document(Path("MockData/unstructured/course-details.md"))
    chunks = chunker.chunk_document(doc)
    
    # 14 distinct programs should produce chunks
    assert len(chunks) >= 14
    headings = [c.heading for c in chunks]
    assert "PERC Ignite" in headings
    assert "NEET UG" in headings
    assert "One-to-One Tuition" in headings

    # Verify breadcrumb injection
    ignite_chunk = next(c for c in chunks if c.heading == "PERC Ignite")
    assert "# PERC Course Details > ## PERC Ignite" in ignite_chunk.content


def test_chunking_preserves_tables_intact(chunker: SemanticMarkdownChunker):
    loader = DocumentLoader(Path("MockData/unstructured"))
    doc = loader.load_document(Path("MockData/unstructured/comparison.md"))
    chunks = chunker.chunk_document(doc)
    
    # Find chunk with the comparison table
    table_chunk = next((c for c in chunks if "| Feature | PERC |" in c.content), None)
    assert table_chunk is not None
    # Verify table is not split mid-row
    assert "| Batch size |" in table_chunk.content
    assert "| Teaching style |" in table_chunk.content


def test_chunk_ids_are_deterministic(chunker: SemanticMarkdownChunker):
    loader = DocumentLoader(Path("MockData/unstructured"))
    doc = loader.load_document(Path("MockData/unstructured/policies.md"))
    
    chunks_1 = chunker.chunk_document(doc)
    chunks_2 = chunker.chunk_document(doc)
    
    assert [c.chunk_id for c in chunks_1] == [c.chunk_id for c in chunks_2]
