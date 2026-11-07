import os
from fastapi import APIRouter, File, UploadFile, HTTPException, Security, status
from fastapi.concurrency import run_in_threadpool

from app.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from app.security import verify_api_key
from app.schemas import PDFCheckResponse
from app.services import process_pdf_file, PDFProcessingError
from app.utils import secure_temp_path, detect_file_type, cleanup_temp_files

router = APIRouter()


@router.post(
    "/check/upload",
    dependencies=[Security(verify_api_key)],
    response_model=PDFCheckResponse,
)
async def check_pdf_upload(file: UploadFile = File(...)):
    allowed_extensions = {".pdf"}
    ext = os.path.splitext(file.filename.lower())[1] if file.filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="File harus berformat PDF (\.pdf)",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB} MB.",
        )

    temp_doc_path = secure_temp_path(suffix=ext)

    try:
        with open(temp_doc_path, "wb") as f:
            f.write(content)

        file_type = detect_file_type(content)

        if file_type == "pdf":
            pdf_path = temp_doc_path
        else:
            raise HTTPException(status_code=400, detail="Format file tidak dikenali")

        result = await run_in_threadpool(process_pdf_file, pdf_path, file.filename)
        return result
    except PDFProcessingError as e:
        raise HTTPException(status_code=500, detail="Gagal memproses PDF")
    finally:
        cleanup_temp_files(temp_doc_path)
