from pathlib import Path
import pytest
from app.rag.chunker import SemanticMarkdownChunker
from app.rag.loader import DocumentLoader
from app.rag.metadata import MetadataEnricher


@pytest.fixture
def enricher() -> MetadataEnricher:
    return MetadataEnricher()


def test_metadata_category_and_priority(enricher: MetadataEnricher):
    loader = DocumentLoader(Path("MockData/unstructured"))
    chunker = SemanticMarkdownChunker()

    # Test Tier 2 document (authoritative RAG)
    doc_policies = loader.load_document(Path("MockData/unstructured/policies.md"))
    chunks_policies = chunker.chunk_document(doc_policies)
    enriched_policies = enricher.enrich_chunk(chunks_policies[0])
    
    assert enriched_policies.category == "C8_POLICIES"
    assert enriched_policies.source_priority == "authoritative_rag"
    assert enriched_policies.document_type == "policy"

    # Test Tier 1 document (secondary RAG)
    doc_fees = loader.load_document(Path("MockData/unstructured/fees-pricing.md"))
    chunks_fees = chunker.chunk_document(doc_fees)
    enriched_fees = enricher.enrich_chunk(chunks_fees[0])
    
    assert enriched_fees.category == "C3_FEES_PRICING"
    assert enriched_fees.source_priority == "secondary_rag"


def test_safe_course_and_branch_mapping(enricher: MetadataEnricher):
    loader = DocumentLoader(Path("MockData/unstructured"))
    chunker = SemanticMarkdownChunker()

    # Course details should accurately map course_id for specific course chunks
    doc_courses = loader.load_document(Path("MockData/unstructured/course-details.md"))
    chunks = chunker.chunk_document(doc_courses)
    
    ignite_chunk = next(c for c in chunks if c.heading == "PERC Ignite")
    enriched_ignite = enricher.enrich_chunk(ignite_chunk)
    assert enriched_ignite.course_id == "perc-ignite"

    neet_chunk = next(c for c in chunks if c.heading == "NEET UG")
    enriched_neet = enricher.enrich_chunk(neet_chunk)
    cbse_chunk = next(c for c in chunks if c.heading == "CBSE Board Coaching")
    enriched_cbse = enricher.enrich_chunk(cbse_chunk)
    assert enriched_cbse.course_id == "cbse-board-coaching"

    icse_chunk = next(c for c in chunks if c.heading == "ICSE Board Coaching")
    enriched_icse = enricher.enrich_chunk(icse_chunk)
    assert enriched_icse.course_id == "icse-board-coaching"

    # Global policy chunk must NOT hallucinate course_id or branch_id
    doc_policies = loader.load_document(Path("MockData/unstructured/policies.md"))
    chunks_policies = chunker.chunk_document(doc_policies)
    enriched_policy = enricher.enrich_chunk(chunks_policies[0])
    assert enriched_policy.course_id is None
    assert enriched_policy.branch_id is None
