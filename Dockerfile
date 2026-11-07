
# syntax=docker/dockerfile:1

# -----------------------------------------------------------------------------
# Stage 1: Builder — install Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build tools + LibreOffice system deps for builder stage
RUN rm -rf /var/lib/apt/lists/* \
    && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5 \
    || (sleep 20 && DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=5) \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y --fix-missing \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with app + LibreOffice
# -----------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime system deps for PyMuPDF + LibreOffice
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
    libreoffice \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy modular application code
COPY app/main.py app/main.py
COPY app/config.py app/config.py
COPY app/security.py app/security.py
COPY app/schemas.py app/schemas.py
COPY app/utils.py app/utils.py
COPY app/services.py app/services.py
COPY app/__init__.py app/__init__.py
COPY app/routers/__init__.py app/routers/__init__.py
COPY app/routers/upload.py app/routers/upload.py
COPY app/routers/url.py app/routers/url.py
COPY app/routers/base64.py app/routers/base64.py

# Create non-root user
RUN groupadd -r appuser \
    && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
