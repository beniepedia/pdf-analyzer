# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required by PyMuPDF (pymupdf)
# Use retry logic and fallback mirror for GitHub Actions network instability
RUN rm -rf /var/lib/apt/lists/* \
    && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5 \
    || (sleep 20 && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5) \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y --fix-missing \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libice6 \
    libsm6 \
    libxt6 \
    librender1 \
    libcups2 \
    ca-certificates \
    curl \
    || (sleep 20 && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y --fix-missing \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libice6 \
    libsm6 \
    libxt6 \
    librender1 \
    libcups2 \
    ca-certificates \
    curl) \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime system dependencies for PyMuPDF
RUN rm -rf /var/lib/apt/lists/* \
    && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5 \
    || (sleep 20 && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5) \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y --fix-missing \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libice6 \
    libsm6 \
    libxt6 \
    librender1 \
    libcups2 \
    ca-certificates \
    curl \
    || (sleep 20 && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y --fix-missing \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libice6 \
    libsm6 \
    libxt6 \
    librender1 \
    libcups2 \
    ca-certificates \
    curl) \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app.py .
COPY .env.example .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Run with uvicorn (production mode, no --reload)
CMD ["uvicorn", "app.main:app", "host", "0.0.0.0", "port", "8000", "--workers", "4"]