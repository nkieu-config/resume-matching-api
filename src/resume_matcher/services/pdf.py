from io import BytesIO

from fastapi import UploadFile
from pypdf import PageObject, PdfReader
from pypdf.errors import PdfReadError

from resume_matcher.config import Settings
from resume_matcher.domain.errors import (
    InvalidPdfError,
    PdfTextUnavailableError,
    PdfTooLargeError,
    UnsupportedPdfError,
)
from resume_matcher.domain.models import ValidatedPdf

CHUNK_SIZE = 64 * 1024
PDF_HEADER_SCAN_BYTES = 1024


async def validate_pdf(upload: UploadFile, settings: Settings) -> ValidatedPdf:
    if upload.content_type != "application/pdf":
        raise UnsupportedPdfError("content type must be application/pdf")

    data = bytearray()
    while chunk := await upload.read(CHUNK_SIZE):
        data.extend(chunk)
        if len(data) > settings.max_pdf_bytes:
            raise PdfTooLargeError(f"PDF exceeds {settings.max_pdf_bytes} bytes")

    immutable_data = bytes(data)
    if b"%PDF-" not in immutable_data[:PDF_HEADER_SCAN_BYTES]:
        raise UnsupportedPdfError("file signature is not PDF")

    try:
        reader = PdfReader(BytesIO(immutable_data), strict=False)
        if reader.is_encrypted:
            raise InvalidPdfError("encrypted PDFs are not supported")
        page_count = len(reader.pages)
        if page_count == 0:
            raise InvalidPdfError("PDF must contain at least one page")
        if page_count > settings.max_pdf_pages:
            raise InvalidPdfError(f"PDF contains more than {settings.max_pdf_pages} pages")
        page_texts = tuple(_extract_page_text(page) for page in reader.pages)
    except InvalidPdfError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise InvalidPdfError("PDF is corrupt or unreadable") from exc

    if not any(text.strip() for text in page_texts):
        raise PdfTextUnavailableError("PDF does not contain extractable resume text")

    return ValidatedPdf(
        data=immutable_data,
        page_count=page_count,
        filename=upload.filename or "resume.pdf",
        page_texts=page_texts,
    )


def _extract_page_text(page: PageObject) -> str:
    if page.get_contents() is None:
        return ""
    text = page.extract_text(extraction_mode="layout") or ""
    return f"{text.rstrip()}\n" if text.strip() else ""
