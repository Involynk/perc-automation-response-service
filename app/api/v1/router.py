from fastapi import APIRouter
from app.api.v1.endpoints import response, whatsapp

api_router = APIRouter()
api_router.include_router(response.router, tags=["response"])
api_router.include_router(whatsapp.router, tags=["whatsapp"])
