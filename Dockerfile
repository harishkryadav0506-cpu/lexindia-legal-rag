# =====================================================================
# LexIndia — Unified Full-Stack Dockerfile (Hugging Face Spaces & Docker)
# Multi-stage build running FastAPI backend and Next.js frontend via supervisord
# Exposes Port 7860 (Hugging Face Spaces default)
# =====================================================================

# Stage 1: Build Next.js Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# Stage 2: Final Full-Stack Runtime
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860

WORKDIR /app

# Install system dependencies, Node.js, and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python package dependencies
COPY pyproject.toml /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Copy application backend code, data, and scripts
COPY src/ /app/src/
COPY data/ /app/data/
COPY scripts/ /app/scripts/
COPY docker/es_init.sh /app/docker/es_init.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend /app/frontend

RUN chmod +x /app/docker/es_init.sh

EXPOSE 7860
EXPOSE 8000
EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=5s --retries=5 --start-period=40s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
