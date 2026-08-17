from fastapi import FastAPI
from app.api.v1.router import api_router

app = FastAPI(
    title="PERC Response Service",
    description="Intelligent AI response service for PERC educational institute queries",
    version="1.0.0",
)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Readiness and liveness probe endpoint."""
    return {"status": "healthy"}


# Mount API v1 router under /api/v1 as well as root for direct endpoint access
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="")
