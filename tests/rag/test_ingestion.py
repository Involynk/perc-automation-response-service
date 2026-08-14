from pathlib import Path
import pytest
from app.rag.ingestion import KnowledgeIngestionPipeline


def test_dry_run_ingestion_metrics():
    pipeline = KnowledgeIngestionPipeline(
        unstructured_dir=Path("MockData/unstructured")
    )
    summary = pipeline.run_ingestion(dry_run=True)
    
    assert summary.total_files_discovered == 18
    assert summary.eligible_files_processed == 15
    assert summary.tier_3_files_skipped == 3
    assert summary.total_chunks_created > 100
    assert summary.vector_dimension == 384
    assert summary.upserted_count == summary.total_chunks_created


def test_ingestion_idempotency():
    pipeline = KnowledgeIngestionPipeline(
        unstructured_dir=Path("MockData/unstructured")
    )
    chunks_run_1 = pipeline.process_all_documents()
    chunks_run_2 = pipeline.process_all_documents()

    assert len(chunks_run_1) == len(chunks_run_2)
    assert [c.chunk_id for c in chunks_run_1] == [c.chunk_id for c in chunks_run_2]
