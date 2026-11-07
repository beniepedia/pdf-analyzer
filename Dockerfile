
# syntax=docker/dockerfile:1

# -------------------------------------------------------------
# Stage 1: Builder
# -------------------------------------------------------------
FROM python:3.11-slim-trixie AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update -o Acquire::Retries=5 \
    && DEBIAN_FRONTEND=noninteractive apt-get install \
       -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# -------------------------------------------------------------
# Stage 2: Runtime
# -------------------------------------------------------------
FROM python:3.11-slim-trixie

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Debian 13 (Trixie) compatible runtime libraries
RUN apt-get update -o Acquire::Retries=5 \
    && DEBIAN_FRONTEND=noninteractive apt-get install \
       -y --no-install-recommends \
       libglib2.0-0t64 \
       libfontconfig1 \
       libfreetype6 \
       libx11-6 \
       libxext6 \
       libxfixes3 \
       libice6 \
       libsm6 \
       libxt6 \
       librender1 \
       libcups2t64 \
       ca-certificates \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY app/ ./app/

# Create non-root user
RUN groupadd -r appuser \
    && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
