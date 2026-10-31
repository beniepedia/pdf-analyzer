import os
import base64
import logging
import tempfile
import uuid
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

import pymupdf  # PyMuPDF
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Security, status, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ---------------------------------------------------------------------------
# Load environment variables from .env file
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY_NAME = "X-API-Key"
VALID_API_KEYS = {
    key for key in [
        os.getenv("API_KEY_1"),
        os.getenv("API_KEY_2"),
    ] if key
}

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "15"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# SSRF protection: blocked networks (localhost + private IP ranges)
# ---------------------------------------------------------------------------
BLOCKED_NETWORKS = [
    ip_network("127.0.0.0/8"),    # IPv4 localhost
    ip_network("10.0.0.0/8"),     # Private class A
    ip_network("172.16.0.0/12"),  # Private class B
    ip_network("192.168.0.0/16"), # Private class C
    ip_network("::1/128"),        # IPv6 localhost
    ip_network("fc00::/7"),       # IPv6 unique local
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pdf-analyzer")

# ---------------------------------------------------------------------------
# Security: API Key header
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Dependency function to check API Key in HTTP Headers."""
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key tidak valid atau tidak ditemukan dalam header 'X-API-Key'.",
        )
    return api_key


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Secure Multi-Method PDF Color Checker API",
    description="API terproteksi API Key untuk mengecek halaman berwarna dan hitam-putih pada PDF via Upload File, URL, atau Base64.",
    version="1.2.0",
)

# CORS middleware — hanya origin yang diizinkan via env var ALLOWED_ORIGINS
# Contoh: ALLOWED_ORIGINS=https://backend-anda.com,https://admin.anda.com
_allowed_origins = [
    origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if _allowed_origins else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class PDFProcessingError(Exception):
    """Raised when PDF processing fails."""


# ---------------------------------------------------------------------------
# Helper: SSRF-safe URL check
# ---------------------------------------------------------------------------
def is_ssrf_safe(url: str) -> bool:
    """Return True if URL is allowed (http/https only, no localhost/private IP)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            ip = ip_address(hostname)
        except ValueError:
            # Hostname (not raw IP) — allow, but could be extended with DNS check
            return True
        for network in BLOCKED_NETWORKS:
            if ip in network:
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helper: secure temporary file path (unique per request)
# ---------------------------------------------------------------------------
def secure_temp_path(suffix: str = ".pdf") -> str:
    return os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}{suffix}")


# ---------------------------------------------------------------------------
# Helper: process PDF file (blocking, runs in thread pool)
# ---------------------------------------------------------------------------
def process_pdf_file(file_path: str, identifier: str):
    try:
        with pymupdf.open(file_path) as doc:
            total_pages = len(doc)
            color_pages = 0
            bw_pages = 0
            detail_halaman = []

            for page_num in range(total_pages):
                page = doc[page_num]
                pix = page.get_pixmap()

                if pix.n < 3:
                    bw_pages += 1
                    detail_halaman.append({"page": page_num + 1, "type": "Hitam-Putih"})
                else:
                    is_color = False
                    step_y = max(1, pix.h // 20)
                    step_x = max(1, pix.w // 20)

                    for y in range(0, pix.h, step_y):
                        for x in range(0, pix.w, step_x):
                            pixel = pix.pixel(x, y)
                            r, g, b = pixel[0], pixel[1], pixel[2]
                            if not (r == g == b):
                                is_color = True
                                break
                        if is_color:
                            break

                    if is_color:
                        color_pages += 1
                        detail_halaman.append({"page": page_num + 1, "type": "color"})
                    else:
                        bw_pages += 1
                        detail_halaman.append({"page": page_num + 1, "type": "bw"})

        return {
            "source": identifier,
            "total_pages": total_pages,
            "color_pages": color_pages,
            "bw_pages": bw_pages,
            "details": detail_halaman,
        }
    except Exception as e:
        logger.error(f"Gagal memproses PDF {identifier}: {str(e)}")
        raise PDFProcessingError(str(e))


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class UrlRequest(BaseModel):
    pdf_url: str


class Base64Request(BaseModel):
    base64_data: str


class PageDetail(BaseModel):
    page: int
    type: str


class PDFCheckResponse(BaseModel):
    source: str
    total_pages: int
    color_pages: int
    bw_pages: int
    details: list[PageDetail]


# ---------------------------------------------------------------------------
# Route 1: Upload File (Multipart Form-Data)
# ---------------------------------------------------------------------------
@app.post(
    "/check/upload",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
@limiter.limit("10/minute")
async def check_pdf_upload(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File harus berformat PDF (.pdf)")

    # Read content and enforce size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB} MB.",
        )

    temp_path = secure_temp_path()
    try:
        # Write file in thread pool to avoid blocking the event loop
        def _write_file():
            with open(temp_path, "wb") as f:
                f.write(content)

        await run_in_threadpool(_write_file)
        logger.info(f"File uploaded: {file.filename} ({len(content)} bytes)")

        result = await run_in_threadpool(process_pdf_file, temp_path, file.filename)
        return result
    except PDFProcessingError as e:
        logger.error(f"Gagal memproses PDF {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal memproses PDF")
    finally:
        def _remove_file():
            if os.path.exists(temp_path):
                os.remove(temp_path)

        await run_in_threadpool(_remove_file)


# ---------------------------------------------------------------------------
# Route 2: URL (JSON Body)
# ---------------------------------------------------------------------------
@app.post(
    "/check/url",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
@limiter.limit("10/minute")
async def check_pdf_url(request: Request, data: UrlRequest):
    if not is_ssrf_safe(data.pdf_url):
        raise HTTPException(
            status_code=400,
            detail="URL tidak diizinkan (hanya http/https, tidak boleh mengarah ke localhost atau jaringan internal).",
        )

    temp_path = secure_temp_path()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(data.pdf_url, follow_redirects=True, timeout=30.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail="Gagal mendownload PDF dari URL tersebut.",
                )

            content_type = response.headers.get("content-type", "")
            if "application/pdf" not in content_type:
                raise HTTPException(
                    status_code=400,
                    detail="URL tidak mengarah ke file PDF (Content-Type bukan application/pdf).",
                )

            file_content = response.content
            if len(file_content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB} MB.",
                )

        def _write_file():
            with open(temp_path, "wb") as f:
                f.write(file_content)

        await run_in_threadpool(_write_file)
        logger.info(f"PDF downloaded from: {data.pdf_url} ({len(file_content)} bytes)")

        result = await run_in_threadpool(process_pdf_file, temp_path, data.pdf_url)
        return result
    except PDFProcessingError as e:
        logger.error(f"Gagal memproses PDF dari {data.pdf_url}: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal memproses PDF")
    finally:
        def _remove_file():
            if os.path.exists(temp_path):
                os.remove(temp_path)

        await run_in_threadpool(_remove_file)


# ---------------------------------------------------------------------------
# Route 3: Base64 String (JSON Body)
# ---------------------------------------------------------------------------
@app.post(
    "/check/base64",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
@limiter.limit("10/minute")
async def check_pdf_base64(request: Request, data: Base64Request):
    temp_path = secure_temp_path()
    try:
        b64_string = data.base64_data
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]

        pdf_bytes = base64.b64decode(b64_string)

        if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB} MB.",
            )

        def _write_file():
            with open(temp_path, "wb") as f:
                f.write(pdf_bytes)

        await run_in_threadpool(_write_file)
        logger.info(f"PDF decoded from base64 ({len(pdf_bytes)} bytes)")

        result = await run_in_threadpool(process_pdf_file, temp_path, "base64_string")
        return result
    except Exception as e:
        logger.error(f"Gagal mendecode Base64: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Gagal mendecode Base64 atau memproses PDF",
        )
    finally:
        def _remove_file():
            if os.path.exists(temp_path):
                os.remove(temp_path)

        await run_in_threadpool(_remove_file)