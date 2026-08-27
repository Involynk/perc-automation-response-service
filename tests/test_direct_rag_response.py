import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.schemas.request import ResponseRequest
from app.schemas.agent import RetrievedDocument
from app.services.rag_response_service import RAGResponseService


def test_direct_rag_response_flow():
    """Verify direct RAG response generation flow:
    1. Fetches conversation history from database.
    2. Builds context-aware search query.
    3. Performs vector/hybrid retrieval from knowledge base.
    4. Generates grounded response with LLM.
    5. Returns formatted ResponseResponse.
    """
    mock_db = MagicMock(spec=Session)

    # 1. Mock DB conversation history
    mock_history = [
        {"direction": "inbound", "content": "Hi, I am looking for 11th standard coaching."},
        {"direction": "outbound", "content": "Hello! PERC offers coaching for JEE, NEET, and KCET."},
    ]

    # 2. Mock RAG retrieved documents
    mock_docs = [
        RetrievedDocument(
            doc_id="doc_cet_1",
            chunk_id="chunk_1",
            source_file="karnataka-cet-programs.md",
            content="PERC CET Coaching Program covers Physics, Chemistry, and Mathematics with weekly mock tests and personalized doubt solving.",
            relevance_score=0.92,
            metadata={"category": "courses"},
        )
    ]

    service = RAGResponseService(db=mock_db)

    req = ResponseRequest(
        session_id="lead_ee904daf-9315-4cce-a68fc3d659c8",
        message="Cet",
        metadata={"lead_id": "ee904daf-9315-4cce-a68fc3d659c8", "channel": "whatsapp", "is_new_lead": True},
    )

    with patch("app.services.rag_response_service.ConversationHistoryRepository") as mock_repo_cls, \
         patch("app.services.rag_response_service.KnowledgeRetriever") as mock_retriever_cls, \
         patch.object(service, "_get_llm_client") as mock_get_llm:

        mock_repo = MagicMock()
        mock_repo.get_conversation_history.return_value = mock_history
        mock_repo_cls.return_value = mock_repo

        mock_retriever = MagicMock()
        mock_retriever.search.return_value = mock_docs
        mock_retriever_cls.return_value = mock_retriever

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"answer": "PERC offers comprehensive Karnataka CET coaching for Class 11 and 12 with comprehensive mock tests and expert faculty.", "confidence": 0.95}'
        mock_get_llm.return_value = mock_llm

        res = service.generate_response(request=req, db=mock_db)

        # Assertions
        assert res.session_id == "lead_ee904daf-9315-4cce-a68fc3d659c8"
        assert res.status == "success"
        assert "Karnataka CET" in res.answer or "PERC" in res.answer
        assert res.sources == ["karnataka-cet-programs.md"]

        # Verify DB history was fetched for the correct lead_id
        mock_repo.get_conversation_history.assert_called_once_with("ee904daf-9315-4cce-a68fc3d659c8")

        # Verify contextual query was sent to retriever
        mock_retriever.search.assert_called_once()
        search_args = mock_retriever.search.call_args[1]
        assert "Cet" in search_args["query"]
