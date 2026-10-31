import os
import tempfile
import uuid


def secure_temp_path(suffix: str = ".pdf") -> str:
    return os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}{suffix}")


def detect_file_type(data: bytes) -> str:
    """Deteksi tipe file berdasarkan magic bytes (header byte).
    Return: 'pdf', 'docx', 'doc', atau 'unknown'
    """
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"  # DOCX is ZIP-based
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return "doc"  # OLE2 Compound Document
    return "unknown"


def cleanup_temp_files(*paths):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass