import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProvider(ABC):
    """Abstract base class for RAG embedding generation."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embeds a single string into a float vector."""
        pass

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of strings into float vectors."""
        return [self.embed_text(t) for t in texts]


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic 384-dimensional embedding provider based on token hashing.
    Outputs unit-normalized float vectors. Used for testing and deterministic baseline ingestion.
    """
    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            # Return zero vector if empty
            return [0.0] * self._dim

        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            tokens = [text.strip()]

        vec = [0.0] * self._dim

        for token in tokens:
            # Hash each token deterministically into vector components
            h = hashlib.sha256(token.encode("utf-8")).digest()
            for idx in range(0, min(len(h), 32), 2):
                val = int.from_bytes(h[idx:idx+2], byteorder="big", signed=True)
                pos = (int.from_bytes(h[idx:idx+2], byteorder="big") + idx) % self._dim
                vec[pos] += float(val) / 32768.0

        # Compute L2 norm
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            return [x / norm for x in vec]
        return [1.0 / math.sqrt(self._dim)] * self._dim


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Local sentence-transformers embedding provider using all-MiniLM-L6-v2 (384 dimensions).
    Lazy-loads sentence_transformers on initialization.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._dim = 384
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            if hasattr(self.model, "get_embedding_dimension"):
                self._dim = self.model.get_embedding_dimension()
            else:
                self._dim = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with `pip install sentence-transformers` or use DeterministicMockEmbeddingProvider."
            )

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


def get_embedding_provider(provider_type: Optional[str] = None) -> EmbeddingProvider:
    """
    Factory function returning the active embedding provider.
    Defaults to DeterministicMockEmbeddingProvider to avoid downloading heavy PyTorch/SentenceTransformers
    models that exceed Render's 512MB RAM memory limit (preventing Exit 137 OOM kills).
    """
    import os
    provider = provider_type or os.getenv("EMBEDDING_PROVIDER") or "mock"
    if provider in ("sentence-transformers", "production"):
        try:
            return SentenceTransformerEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                f"SentenceTransformers unavailable ({exc}). Falling back to DeterministicMockEmbeddingProvider."
            )
            return DeterministicMockEmbeddingProvider(dim=384)
    return DeterministicMockEmbeddingProvider(dim=384)

