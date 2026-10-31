
# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencies untuk build Python packages
RUN set -eux; \
    (apt-get update -o Acquire::Retries=5 || \
    (sleep 10 && apt-get update -o Acquire::Retries=5)); \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


# Runtime
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Runtime libraries
RUN set -eux; \
    (apt-get update -o Acquire::Retries=5 || \
    (sleep 10 && apt-get update -o Acquire::Retries=5)); \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libxext6 \
        libxfixes3 \
        libice6 \
        libsm6 \
        libxt6 \
        libxrender1 \
        libcups2 \
        ca-certificates \
        curl; \
    rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY --from=builder /usr/local/lib/python3.11/site-packages \
    /usr/local/lib/python3.11/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY app.py .

# Non-root user
RUN groupadd -r appuser \
    && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
