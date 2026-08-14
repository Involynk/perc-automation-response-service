from pathlib import Path
import pytest
from app.rag.loader import DocumentLoader, TIER_3_EXCLUDED_FILES


@pytest.fixture
def unstructured_dir() -> Path:
    return Path("MockData/unstructured")


def test_loader_discovery_all_files(unstructured_dir: Path):
    loader = DocumentLoader(unstructured_dir)
    all_docs = loader.discover_eligible_documents(include_tier_3=True)
    assert len(all_docs) == 18
    filenames = {d.filename for d in all_docs}
    assert "policies.md" in filenames
    assert "course-details.md" in filenames
    assert "multi-intent.md" in filenames


def test_loader_tier_3_exclusion(unstructured_dir: Path):
    loader = DocumentLoader(unstructured_dir)
    eligible_docs = loader.discover_eligible_documents(include_tier_3=False)
    assert len(eligible_docs) == 15
    for doc in eligible_docs:
        assert doc.filename not in TIER_3_EXCLUDED_FILES
        assert doc.tier in (1, 2)


def test_loader_utf8_and_content_preservation(unstructured_dir: Path):
    loader = DocumentLoader(unstructured_dir)
    policies_doc = loader.load_document(unstructured_dir / "policies.md")
    assert policies_doc.document_id == "policies"
    assert "Academic Policies" in policies_doc.raw_content
    assert policies_doc.tier == 2
