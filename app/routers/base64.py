import base64
from fastapi import APIRouter, HTTPException, Security, status
from fastapi.concurrency import run_in_threadpool

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from app.security import verify_api_key
from app.schemas import Base64Request, PDFCheckResponse
from app.services import process_pdf_file, convert_doc_to_pdf, PDFProcessingError, LibreOfficeError
from app.utils import secure_temp_path, detect_file_type, cleanup_temp_files

router = APIRouter()


@router.post(
    "/check/base64",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
async def check_pdf_base64(data: Base64Request):
    temp_doc_path = None
    temp_pdf_path = None

    try:
        b64_string = data.base64_data
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]

        file_bytes = base64.b64decode(b64_string)

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB} MB.",
            )

        file_type = detect_file_type(file_bytes)

        if file_type == "pdf":
            temp_doc_path = secure_temp_path(suffix=".pdf")
            with open(temp_doc_path, "wb") as f:
                f.write(file_bytes)
            pdf_path = temp_doc_path
        elif file_type in ("doc", "docx"):
            temp_doc_path = secure_temp_path(suffix=f".{file_type}")
            with open(temp_doc_path, "wb") as f:
                f.write(file_bytes)
            pdf_path = convert_doc_to_pdf(temp_doc_path)
            temp_pdf_path = pdf_path
        else:
            raise HTTPException(status_code=400, detail="Format file tidak didukung")

        result = await run_in_threadpool(process_pdf_file, pdf_path, "base64_string")
        return result
    except PDFProcessingError as e:
        raise HTTPException(status_code=500, detail="Gagal memproses PDF")
    except LibreOfficeError as e:
        raise HTTPException(status_code=500, detail="Gagal mengonversi dokumen ke PDF")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Gagal mendecode Base64 atau memproses PDF",
        )
    finally:
        cleanup_temp_files(temp_doc_path, temp_pdf_path)