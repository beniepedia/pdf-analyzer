from pydantic import BaseModel


class UrlRequest(BaseModel):
    pdf_url: str


class Base64Request(BaseModel):
    base64_data: str


class PageDetail(BaseModel):
    page: int
    type: str
    paper_size_mm: str | None = None
    paper_size_inch: str | None = None
    paper_size_standard: str | None = None


class PDFCheckResponse(BaseModel):
    source: str
    total_pages: int
    color_pages: int
    bw_pages: int
    paper_size_mm: str | None = None
    paper_size_inch: str | None = None
    paper_size_standard: str | None = None
    details: list[PageDetail]