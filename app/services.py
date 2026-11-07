import base64
import logging
import os
import shutil
import subprocess
import glob

import pymupdf

from app.config import LIBREOFFICE_TIMEOUT, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from app.utils import detect_file_type

logger = logging.getLogger("pdf-analyzer")


class PDFProcessingError(Exception):
    """Raised when PDF processing fails."""


class LibreOfficeError(Exception):
    """Raised when DOC/DOCX to PDF conversion fails."""


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
                        detail_halaman.append({"page": page_num + 1, "type": "Berwarna"})
                    else:
                        bw_pages += 1
                        detail_halaman.append({"page": page_num + 1, "type": "Hitam-Putih"})

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


def convert_doc_to_pdf(input_path: str, timeout: int | None = None) -> str:
    """Mengonversi DOC/DOCX ke PDF via LibreOffice headless.
    Returns path ke file PDF hasil konversi."""
    if timeout is None:
        timeout = LIBREOFFICE_TIMEOUT

    libreoffice_bin = shutil.which("libreoffice")
    if not libreoffice_bin:
        raise LibreOfficeError("LibreOffice tidak ditemukan di sistem.")

    output_dir = os.path.dirname(input_path)
    try:
        result = subprocess.run(
            [
                libreoffice_bin,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                output_dir,
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise LibreOfficeError("Konversi DOC/DOCX melebihi batas waktu.")
    except Exception as e:
        raise LibreOfficeError(f"Gagal menjalankan LibreOffice: {str(e)}")

    if result.returncode != 0:
        raise LibreOfficeError(f"LibreOffice gagal: {result.stderr.strip()}")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

    if not os.path.exists(pdf_path):
        matches = glob.glob(os.path.join(output_dir, f"{base_name}*.pdf"))
        if matches:
            pdf_path = matches[0]
        else:
            raise LibreOfficeError("File PDF hasil konversi tidak ditemukan.")

    return pdf_path