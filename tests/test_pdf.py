from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas
from starlette.datastructures import Headers

from resume_matcher.config import Settings
from resume_matcher.domain.errors import (
    InvalidPdfError,
    PdfTextUnavailableError,
    PdfTooLargeError,
    UnsupportedPdfError,
)
from resume_matcher.services.pdf import validate_pdf

IMAGE_ONLY_RESUME_BYTES = Path("tests/fixtures/image_only_resume.pdf").read_bytes()


def build_pdf(page_count: int = 1, encrypted: bool = False) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("secret")
    writer.write(output)
    return output.getvalue()


def build_text_pdf() -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    canvas.drawString(72, 720, "Built a Python API")
    canvas.showPage()
    canvas.drawString(72, 720, "Deployed with Docker")
    canvas.save()
    return output.getvalue()


def build_positioned_text_pdf() -> bytes:
    output = BytesIO()
    canvas = Canvas(output)
    canvas.drawString(72, 720, "Elliott W")
    canvas.drawString(116, 720, "ave Lab")
    canvas.save()
    return output.getvalue()


def make_upload(data: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename="resume.pdf",
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.anyio
async def test_valid_pdf_returns_bytes_and_page_count() -> None:
    data = build_text_pdf()

    result = await validate_pdf(make_upload(data), Settings(_env_file=None))

    assert result.data == data
    assert result.page_count == 2
    assert result.filename == "resume.pdf"


@pytest.mark.anyio
async def test_pdf_without_extractable_text_is_rejected() -> None:
    with pytest.raises(PdfTextUnavailableError):
        await validate_pdf(make_upload(build_pdf()), Settings(_env_file=None))


@pytest.mark.anyio
async def test_image_only_resume_fixture_is_rejected() -> None:
    with pytest.raises(PdfTextUnavailableError):
        await validate_pdf(make_upload(IMAGE_ONLY_RESUME_BYTES), Settings(_env_file=None))


@pytest.mark.anyio
async def test_valid_pdf_returns_extractable_text_by_page() -> None:
    result = await validate_pdf(make_upload(build_text_pdf()), Settings(_env_file=None))

    assert result.page_texts == ("Built a Python API\n", "Deployed with Docker\n")


@pytest.mark.anyio
async def test_positioned_text_is_extracted_in_reading_order() -> None:
    result = await validate_pdf(make_upload(build_positioned_text_pdf()), Settings(_env_file=None))

    assert result.page_texts == ("Elliott Wave Lab\n",)


@pytest.mark.anyio
async def test_wrong_content_type_is_rejected() -> None:
    with pytest.raises(UnsupportedPdfError):
        await validate_pdf(make_upload(build_pdf(), "text/plain"), Settings(_env_file=None))


@pytest.mark.anyio
async def test_non_pdf_bytes_are_rejected() -> None:
    with pytest.raises(UnsupportedPdfError):
        await validate_pdf(make_upload(b"not a pdf"), Settings(_env_file=None))


@pytest.mark.anyio
async def test_oversized_pdf_is_rejected_while_streaming() -> None:
    settings = Settings(max_pdf_bytes=8, _env_file=None)

    with pytest.raises(PdfTooLargeError):
        await validate_pdf(make_upload(build_pdf()), settings)


@pytest.mark.anyio
async def test_encrypted_pdf_is_rejected() -> None:
    with pytest.raises(InvalidPdfError, match="encrypted"):
        await validate_pdf(make_upload(build_pdf(encrypted=True)), Settings(_env_file=None))


@pytest.mark.anyio
async def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(InvalidPdfError, match="corrupt"):
        await validate_pdf(make_upload(b"%PDF-corrupt"), Settings(_env_file=None))


@pytest.mark.anyio
async def test_zero_page_pdf_is_rejected() -> None:
    with pytest.raises(InvalidPdfError, match="at least one page"):
        await validate_pdf(make_upload(build_pdf(0)), Settings(_env_file=None))


@pytest.mark.anyio
async def test_page_limit_is_enforced() -> None:
    with pytest.raises(InvalidPdfError, match="more than 20 pages"):
        await validate_pdf(make_upload(build_pdf(21)), Settings(_env_file=None))
