import asyncio
import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.events.kafka_manager import kafka_manager


async def _keep_alive_loop():
    """Periodically pings self every 5 minutes to prevent Render free instance idle sleep."""
    url = os.getenv("RENDER_EXTERNAL_URL") or "https://perc-automation-response-service.onrender.com/health"
    await asyncio.sleep(30)  # Wait 30 seconds after startup
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                print(f"⏰ [KeepAlive] Self-ping to {url} -> Status {resp.status_code}", flush=True)
        except Exception as err:
            print(f"⚠️ [KeepAlive] Self-ping error: {err}", flush=True)
        await asyncio.sleep(300)  # Ping every 5 minutes (300 seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup lifecycle
    await kafka_manager.start()
    keep_alive_task = asyncio.create_task(_keep_alive_loop())
    yield
    # Application shutdown lifecycle
    keep_alive_task.cancel()
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
