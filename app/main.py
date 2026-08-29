from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import api_router


from app.events.kafka_manager import kafka_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup lifecycle
    await kafka_manager.start()
    yield
    # Application shutdown lifecycle
    await kafka_manager.stop()


app = FastAPI(
    title="PERC Response Service",
    description="Intelligent AI response service for PERC educational institute queries",
    version="1.0.0",
    lifespan=lifespan,
)


@app.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
def health_check() -> dict:
    """Readiness and liveness probe endpoint."""
    return {"status": "healthy"}


@app.api_route("/", methods=["GET", "HEAD"], tags=["health"])
def root_check() -> dict:
    """Root health check endpoint for cloud load balancers."""
    return {"status": "healthy", "service": "perc-response-service"}


# Mount API v1 router under /api/v1 as well as root for direct endpoint access
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="")
