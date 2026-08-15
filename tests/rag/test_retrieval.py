import json
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.rag.embeddings import DeterministicMockEmbeddingProvider, SentenceTransformerEmbeddingProvider
from app.rag.hybrid_search import HybridSearch
from app.rag.keyword_search import KeywordSearch
from app.rag.retrieval import KnowledgeRetriever
from app.rag.vector_search import VectorSearch
from app.schemas.agent import RetrievedDocument


@pytest.fixture(scope="module")
def db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def mock_embedding_provider() -> DeterministicMockEmbeddingProvider:
    return DeterministicMockEmbeddingProvider(dim=384)


@pytest.fixture(scope="module")
def retriever(db_session: Session) -> KnowledgeRetriever:
    # Use real production embedding provider for integration verification
    return KnowledgeRetriever(db=db_session, default_top_k=3, default_min_similarity=0.70)


def test_query_embedding_dimension_validation(db_session: Session):
    class InvalidDimProvider(DeterministicMockEmbeddingProvider):
        def embed_text(self, text: str):
            return [0.1] * 128  # Invalid dimension

    bad_retriever = KnowledgeRetriever(db=db_session, embedding_provider=InvalidDimProvider(dim=128))
    with pytest.raises(ValueError, match="expected 384 dimensions"):
        bad_retriever.search_vector("Test query")


def test_empty_query_returns_empty_list(retriever: KnowledgeRetriever):
    assert retriever.search("") == []
    assert retriever.search("   ") == []
    assert retriever.search_vector("") == []
    assert retriever.search_keyword("") == []
    assert retriever.search_hybrid("") == []


def test_vector_search_top_k_clamping(db_session: Session, retriever: KnowledgeRetriever):
    # top_k should clamp between 1 and 5
    res_1 = retriever.search_vector("documents required", top_k=1)
    assert len(res_1) <= 1

    res_10 = retriever.search_vector("documents required", top_k=10)
    assert len(res_10) <= 5


def test_vector_search_cosine_threshold_rejection(retriever: KnowledgeRetriever):
    # Completely unrelated query should yield 0 results with default min_similarity=0.70
    unrelated_res = retriever.search_vector(
        "Recipe for chocolate fudge brownies with walnuts",
        min_similarity=0.70
    )
    assert unrelated_res == []


def test_keyword_search_exact_match(db_session: Session):
    kw_search = KeywordSearch(db_session)
    results = kw_search.search("Aadhar card passport size photographs", top_k=3)
    assert len(results) > 0
    assert any("required-documents.md" in doc.source_file for doc in results)
    assert results[0].relevance_score >= 0.0


def test_hybrid_search_rrf_scoring(db_session: Session):
    hybrid = HybridSearch(db_session, rrf_k=60)
    query_text = "What documents are required for admission?"
    provider = SentenceTransformerEmbeddingProvider("all-MiniLM-L6-v2")
    query_vector = provider.embed_text(query_text)

    results = hybrid.search(query_text=query_text, query_vector=query_vector, top_k=3)
    assert len(results) > 0
    assert any("required-documents.md" in r.source_file for r in results)
    assert results[0].relevance_score <= 1.0
    assert "rrf_raw_score" in results[0].metadata
    assert results[0].metadata["search_mode"] == "hybrid"


def test_category_metadata_filtering(retriever: KnowledgeRetriever):
    # Query hostel query but restrict to C7_REQUIRED_DOCUMENTS
    docs = retriever.search(
        query="hostel accommodation rooms",
        category="C7_REQUIRED_DOCUMENTS",
        min_similarity=0.40
    )
    # If any returned, all must match requested category
    for doc in docs:
        assert doc.metadata["category"] == "C7_REQUIRED_DOCUMENTS"


def test_global_knowledge_searchability(retriever: KnowledgeRetriever):
    # Global documents (e.g. policies.md) have course_id=NULL and branch_id=NULL
    # They should be retrieved when course_id / branch_id filter is passed
    docs = retriever.search(
        query="What is PERC's testing assessment and refund policy?",
        course_id="perc-ignite",
        branch_id="begur-main",
        min_similarity=0.40
    )
    assert len(docs) > 0
    assert any("policies.md" in d.source_file for d in docs)


def test_branch_isolation_prevent_leakage(retriever: KnowledgeRetriever):
    # Begur campus details should NOT be returned if a non-existent or different branch_id is queried
    # (unless it's global knowledge where branch_id IS NULL)
    docs = retriever.search_vector(
        query="Where is the campus located on Begur Road?",
        branch_id="non-existent-branch",
        min_similarity=0.60
    )
    # Any returned documents MUST have branch_id IS NULL (global), never a conflicting branch_id
    for d in docs:
        assert d.metadata.get("branch_id") is None


def test_course_isolation_filter(retriever: KnowledgeRetriever):
    # When course_id='perc-ignite' is requested, any course-specific chunk must be 'perc-ignite' (or global NULL)
    docs = retriever.search(
        query="Tell me about the course curriculum and duration",
        course_id="perc-ignite",
        min_similarity=0.60
    )
    for d in docs:
        c_id = d.metadata.get("course_id")
        assert c_id is None or c_id == "perc-ignite"


def test_evaluation_cases_dataset_integrity():
    cases_file = Path("tests/rag/retrieval_cases.json")
    assert cases_file.exists()
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) >= 12
    for case in cases:
        assert "query" in case
        assert "expected_sources" in case
        assert "should_return_results" in case


def test_retrieval_evaluation_suite(retriever: KnowledgeRetriever):
    """
    Executes the full evaluation suite from retrieval_cases.json and asserts Hit@3 and negative rejection.
    """
    cases_file = Path("tests/rag/retrieval_cases.json")
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    positive_hits = 0
    positive_total = 0
    negative_rejections = 0
    negative_total = 0

    for case in cases:
        query = case["query"]
        expected_sources = case["expected_sources"]
        should_return = case["should_return_results"]
        cat = case.get("category")
        course_id = case.get("course_id")
        branch_id = case.get("branch_id")

        results = retriever.search(
            query=query,
            mode="hybrid",
            top_k=3,
            min_similarity=0.40,
            course_id=course_id,
            branch_id=branch_id,
        )

        if should_return:
            positive_total += 1
            retrieved_sources = [d.source_file for d in results]
            # Check if any expected source is in retrieved sources
            hit = any(exp in retrieved_sources for exp in expected_sources)
            if hit:
                positive_hits += 1
            else:
                pytest.fail(
                    f"Evaluation query failed: '{query}'. Expected {expected_sources}, got {retrieved_sources}"
                )
        else:
            negative_total += 1
            if len(results) == 0:
                negative_rejections += 1
            else:
                pytest.fail(
                    f"Negative query returned unexpected results: '{query}'. Got {[d.source_file for d in results]}"
                )

    hit_rate = (positive_hits / positive_total) * 100 if positive_total > 0 else 0
    assert hit_rate == 100.0, f"Expected 100% Hit@3 on evaluation queries, got {hit_rate}%"
    assert negative_rejections == negative_total, "Negative queries must be rejected with 0 results"
