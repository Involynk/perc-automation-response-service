# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Prevent Python from writing bytecode and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Install system utilities (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies in a cached layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a non-privileged system user for container security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy application source code and configuration
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY MockData/ MockData/
COPY scripts/ scripts/
COPY tests/ tests/
COPY pytest.ini .

# Set ownership to non-root user
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Health check probe against the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production ASGI server launch command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
