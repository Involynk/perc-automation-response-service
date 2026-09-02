from pathlib import Path

from app.rag.extractors import extract_text, UnsupportedDocumentTypeError
from app.rag.ingestion import KnowledgeIngestionPipeline
from app.rag.loader import LoadedDocument
import pytest


def test_extract_markdown_bytes():
    extracted = extract_text("policies.md", b"# Policies\n\nRefunds are not available after 7 days.")
    assert extracted.content_type == "text/markdown"
    assert "Refunds" in extracted.text


def test_extract_html_strips_tags():
    extracted = extract_text("note.html", b"<html><body><h1>Hostel</h1><p>Meals included.</p></body></html>")
    assert "Hostel" in extracted.text
    assert "<p>" not in extracted.text


def test_unsupported_extension():
    with pytest.raises(UnsupportedDocumentTypeError):
        extract_text("photo.png", b"not-an-image")


def test_process_loaded_document_creates_chunks():
    pipeline = KnowledgeIngestionPipeline(unstructured_dir=Path("MockData/unstructured"))
    doc = LoadedDocument(
        document_id="custom-policy",
        filename="custom-policy.md",
        file_path=Path("custom-policy.md"),
        raw_content="# Custom Policy\n\n## Refunds\n\nStudents may request a refund within 7 days of enrollment.",
        tier=2,
    )
    chunks = pipeline.process_loaded_document(doc)
    assert len(chunks) >= 1
    assert chunks[0].document_id == "custom-policy"
    assert chunks[0].source_file == "custom-policy.md"
    assert "Refunds" in chunks[0].content or "refund" in chunks[0].content.lower()
