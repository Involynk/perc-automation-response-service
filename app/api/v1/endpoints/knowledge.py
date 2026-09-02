from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import verify_internal_api_key
from app.db.session import get_db_session
from app.rag.extractors import UnsupportedDocumentTypeError
from app.schemas.knowledge import (
    KnowledgeDocumentUpdate,
    KnowledgeIngestResponse,
    KnowledgeListResponse,
)
from app.services.knowledge_service import KnowledgeBaseService

router = APIRouter()


def get_knowledge_service(db: Session = Depends(get_db_session)) -> KnowledgeBaseService:
    return KnowledgeBaseService(db)


@router.get("/knowledge/documents", response_model=KnowledgeListResponse)
def list_knowledge_documents(
    q: Optional[str] = Query(default=None),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
) -> KnowledgeListResponse:
    documents, total_chunks = service.list_documents(query=q)
    return KnowledgeListResponse(
        documents=[service.to_summary(doc) for doc in documents],
        total=len(documents),
        total_chunks=total_chunks,
    )


@router.get("/knowledge/documents/{document_id}")
def get_knowledge_document(
    document_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
):
    try:
        document = service.get_document(document_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    return service.to_detail(document)


@router.get("/knowledge/documents/{document_id}/chunks")
def list_knowledge_chunks(
    document_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
):
    try:
        chunks = service.list_chunks(document_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    return {"chunks": [service.to_chunk_view(chunk) for chunk in chunks]}


@router.post("/knowledge/documents", response_model=KnowledgeIngestResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    document_id: Optional[str] = Form(default=None),
    category: Optional[str] = Form(default=None),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
) -> KnowledgeIngestResponse:
    data = await file.read()
    try:
        document, chunks_indexed = service.ingest_upload(
            filename=file.filename or "untitled.md",
            data=data,
            content_type=file.content_type,
            title=title,
            document_id=document_id,
            category=category,
        )
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document saved but indexing failed: {exc}",
        )
    return KnowledgeIngestResponse(
        document=service.to_detail(document),
        chunks_indexed=chunks_indexed,
        vector_dimension=service.pipeline.embedding_provider.dimension,
        message="Document indexed. The response service will use this knowledge on the next query.",
    )


@router.put("/knowledge/documents/{document_id}", response_model=KnowledgeIngestResponse)
def update_knowledge_document(
    document_id: str,
    payload: KnowledgeDocumentUpdate,
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
) -> KnowledgeIngestResponse:
    try:
        document, chunks_indexed = service.update_document(document_id, payload)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {exc}",
        )
    return KnowledgeIngestResponse(
        document=service.to_detail(document),
        chunks_indexed=chunks_indexed,
        vector_dimension=service.pipeline.embedding_provider.dimension,
        message="Knowledge updated. Changes are live without redeploying the service.",
    )


@router.post("/knowledge/documents/{document_id}/reindex", response_model=KnowledgeIngestResponse)
def reindex_knowledge_document(
    document_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
) -> KnowledgeIngestResponse:
    try:
        document, chunks_indexed = service.reindex_document(document_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reindex failed: {exc}",
        )
    return KnowledgeIngestResponse(
        document=service.to_detail(document),
        chunks_indexed=chunks_indexed,
        vector_dimension=service.pipeline.embedding_provider.dimension,
        message="Document re-embedded. Retrieval will use the new vectors immediately.",
    )


@router.delete("/knowledge/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_document(
    document_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_service),
    _: None = Depends(verify_internal_api_key),
) -> None:
    try:
        service.delete_document(document_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
