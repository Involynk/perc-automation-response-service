from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.endpoints.knowledge import get_knowledge_service
from app.schemas.knowledge import (
    KnowledgeChunkView,
    KnowledgeDocumentDetail,
    KnowledgeDocumentSummary,
)


class FakeKnowledgeService:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.document = KnowledgeDocumentDetail(
            id="policies",
            filename="policies.md",
            title="Policies",
            content_type="text/markdown",
            category="policy",
            chunk_count=2,
            token_count=80,
            status="indexed",
            error_message=None,
            created_at=now,
            updated_at=now,
            raw_content="# Policies\n\nNo refunds after 7 days.",
        )
        self.pipeline = SimpleNamespace(embedding_provider=SimpleNamespace(dimension=384))

    def list_documents(self, query=None):
        return [self.document], self.document.chunk_count

    def get_document(self, document_id: str):
        if document_id != self.document.id:
            raise KeyError(document_id)
        return self.document

    def list_chunks(self, document_id: str):
        self.get_document(document_id)
        return [
            SimpleNamespace(
                id="policies_chk_000_abc",
                section="Policies",
                heading="Policies",
                chunk_index=0,
                token_count=40,
                category="C8_POLICIES",
                chunk_content=self.document.raw_content,
            )
        ]

    def ingest_upload(self, **kwargs):
        return self.document, 2

    def update_document(self, document_id, payload):
        self.get_document(document_id)
        if payload.raw_content:
            self.document.raw_content = payload.raw_content
        return self.document, 2

    def reindex_document(self, document_id):
        self.get_document(document_id)
        return self.document, 2

    def delete_document(self, document_id):
        self.get_document(document_id)

    def to_summary(self, document):
        return KnowledgeDocumentSummary.model_validate(document, from_attributes=True)

    def to_detail(self, document):
        return KnowledgeDocumentDetail.model_validate(document, from_attributes=True)

    def to_chunk_view(self, chunk):
        return KnowledgeChunkView(
            id=chunk.id,
            section=chunk.section,
            heading=chunk.heading,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            category=chunk.category,
            chunk_content=chunk.chunk_content,
        )


@pytest.fixture
def client():
    fake = FakeKnowledgeService()
    app.dependency_overrides[get_knowledge_service] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_knowledge_ui_is_served(client):
    response = client.get("/knowledge")
    assert response.status_code == 200
    assert "PERC Knowledge Base" in response.text


def test_list_knowledge_documents(client):
    response = client.get("/api/v1/knowledge/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["documents"][0]["id"] == "policies"


def test_get_knowledge_document(client):
    response = client.get("/api/v1/knowledge/documents/policies")
    assert response.status_code == 200
    assert "No refunds" in response.json()["raw_content"]


def test_upload_knowledge_document(client):
    response = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("policies.md", b"# Policies\n\nUpdated.", "text/markdown")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["chunks_indexed"] == 2
    assert "redeploy" not in body["message"].lower() or "live" in body["message"].lower() or "indexed" in body["message"].lower()


def test_update_and_delete_knowledge_document(client):
    update = client.put(
        "/api/v1/knowledge/documents/policies",
        json={"raw_content": "# Policies\n\nUpdated refund window."},
    )
    assert update.status_code == 200
    deleted = client.delete("/api/v1/knowledge/documents/policies")
    assert deleted.status_code == 204


def test_missing_document_returns_404(client):
    response = client.get("/api/v1/knowledge/documents/missing")
    assert response.status_code == 404
