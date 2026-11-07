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


# ---------------------------------------------------------------------------
# Paper size standards (width x height in mm, tolerance ±2 mm)
# ---------------------------------------------------------------------------
PAPER_SIZES_MM = {
    "A0": (841, 1189),
    "A1": (594, 841),
    "A2": (420, 594),
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210),
    "A6": (105, 148),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "Executive": (184.2, 266.7),
    "Folio": (210, 330),
}

TOLERANCE_MM = 2.0


def points_to_mm(points: float) -> float:
    return points * 25.4 / 72.0


def points_to_inch(points: float) -> float:
    return points / 72.0


def detect_paper_size(width_mm: float, height_mm: float) -> str | None:
    """Deteksi standar kertas berdasarkan dimensi mm (toleransi ±2 mm)."""
    # Normalisasi: pastikan width <= height untuk pencocokan portrait/landscape
    w, h = sorted([width_mm, height_mm])
    for name, (std_w, std_h) in PAPER_SIZES_MM.items():
        if abs(w - std_w) <= TOLERANCE_MM and abs(h - std_h) <= TOLERANCE_MM:
            return name
    return None


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

                # --- Deteksi ukuran kertas ---
                rect = page.rect
                width_points = rect.width
                height_points = rect.height
                width_mm = round(points_to_mm(width_points), 1)
                height_mm = round(points_to_mm(height_points), 1)
                width_inch = round(points_to_inch(width_points), 2)
                height_inch = round(points_to_inch(height_points), 2)
                paper_standard = detect_paper_size(width_mm, height_mm)

                if pix.n < 3:
                    bw_pages += 1
                    detail_halaman.append({
                        "page": page_num + 1,
                        "type": "BW",
                        "paper_size_mm": f"{width_mm} × {height_mm}",
                        "paper_size_inch": f"{width_inch} × {height_inch}",
                        "paper_size_standard": paper_standard,
                    })
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
                        detail_halaman.append({
                            "page": page_num + 1,
                            "type": "CL",
                            "paper_size_mm": f"{width_mm} × {height_mm}",
                            "paper_size_inch": f"{width_inch} × {height_inch}",
                            "paper_size_standard": paper_standard,
                        })
                    else:
                        bw_pages += 1
                        detail_halaman.append({
                            "page": page_num + 1,
                            "type": "BW",
                            "paper_size_mm": f"{width_mm} × {height_mm}",
                            "paper_size_inch": f"{width_inch} × {height_inch}",
                            "paper_size_standard": paper_standard,
                        })

            # --- Hitung ukuran kertas di level root (Opsi C: Mixed) ---
            all_standards = {d["paper_size_standard"] for d in detail_halaman if d["paper_size_standard"]}
            if len(all_standards) == 1:
                root_standard = next(iter(all_standards))
            elif len(all_standards) > 1:
                root_standard = "Mixed"
            else:
                root_standard = None

            first_page = detail_halaman[0] if detail_halaman else None
            root_mm = first_page["paper_size_mm"] if first_page else None
            root_inch = first_page["paper_size_inch"] if first_page else None

        return {
            "source": identifier,
            "total_pages": total_pages,
            "color_pages": color_pages,
            "bw_pages": bw_pages,
            "paper_size_mm": root_mm,
            "paper_size_inch": root_inch,
            "paper_size_standard": root_standard,
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