from pydantic import BaseModel


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