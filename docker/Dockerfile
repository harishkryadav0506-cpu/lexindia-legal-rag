# =====================================================================
# LexIndia — Backend Service Dockerfile
# Python 3.10 slim container for FastAPI API, agents, and retrieval
# =====================================================================

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system utilities and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install Python dependencies
COPY pyproject.toml /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Copy application source code and data assets
COPY src/ /app/src/
COPY data/ /app/data/
COPY scripts/ /app/scripts/
COPY docker/es_init.sh /app/docker/es_init.sh

RUN chmod +x /app/docker/es_init.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
