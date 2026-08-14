import math
import pytest
from app.rag.embeddings import (
    DeterministicMockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
)


def test_embedding_dimension():
    provider = DeterministicMockEmbeddingProvider(dim=384)
    assert provider.dimension == 384
    vec = provider.embed_text("PERC Ignite Class 6 Foundation Course")
    assert len(vec) == 384


def test_embedding_normalization_and_determinism():
    provider = DeterministicMockEmbeddingProvider(dim=384)
    text = "Comprehensive JEE and NEET coaching in Begur Bangalore"
    
    vec1 = provider.embed_text(text)
    vec2 = provider.embed_text(text)
    assert vec1 == vec2

    # Verify L2 norm is ~ 1.0
    norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm, 1e-4) == 1.0


def test_batch_embeddings():
    provider = get_embedding_provider("mock")
    texts = ["Course A", "Course B", "Course C"]
    batch_vecs = provider.embed_batch(texts)
    assert len(batch_vecs) == 3
    for v in batch_vecs:
        assert len(v) == 384


def test_get_embedding_provider_factory():
    mock_provider = get_embedding_provider("mock")
    assert isinstance(mock_provider, DeterministicMockEmbeddingProvider)
    assert mock_provider.dimension == 384

    # Invalid provider must raise ValueError
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        get_embedding_provider("invalid-provider-name")
