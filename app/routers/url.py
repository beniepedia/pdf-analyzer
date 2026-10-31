import httpx
from fastapi import APIRouter, HTTPException, Security, status
from fastapi.concurrency import run_in_threadpool

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from app.security import verify_api_key, is_ssrf_safe
from app.schemas import UrlRequest, PDFCheckResponse
from app.services import process_pdf_file, convert_doc_to_pdf, PDFProcessingError, LibreOfficeError
from app.utils import secure_temp_path, detect_file_type, cleanup_temp_files

router = APIRouter()


@router.post(
    "/check/url",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
async def check_pdf_url(data: UrlRequest):
    if not is_ssrf_safe(data.pdf_url):
        raise HTTPException(
            status_code=400,
            detail="URL tidak diizinkan (hanya http/https, tidak boleh mengarah ke localhost atau jaringan internal).",
        )

    temp_doc_path = None
    temp_pdf_path = None

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

            file_type = detect_file_type(file_content)

            if file_type == "pdf":
                temp_doc_path = secure_temp_path(suffix=".pdf")
                with open(temp_doc_path, "wb") as f:
                    f.write(file_content)
                pdf_path = temp_doc_path
            elif file_type in ("doc", "docx"):
                temp_doc_path = secure_temp_path(suffix=f".{file_type}")
                with open(temp_doc_path, "wb") as f:
                    f.write(file_content)
                pdf_path = convert_doc_to_pdf(temp_doc_path)
                temp_pdf_path = pdf_path
            else:
                raise HTTPException(status_code=400, detail="Format file tidak didukung")

        result = await run_in_threadpool(process_pdf_file, pdf_path, data.pdf_url)
        return result
    except PDFProcessingError as e:
        raise HTTPException(status_code=500, detail="Gagal memproses PDF")
    except LibreOfficeError as e:
        raise HTTPException(status_code=500, detail="Gagal mengonversi dokumen ke PDF")
    finally:
        cleanup_temp_files(temp_doc_path, temp_pdf_path)