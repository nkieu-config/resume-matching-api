from typing import Protocol

import pytest
from httpx import ASGITransport, AsyncClient

from resume_matcher.config import Settings
from resume_matcher.domain.errors import ProviderOutputError, ProviderTimeoutError
from resume_matcher.domain.models import AnalysisResult, ValidatedPdf
from resume_matcher.main import create_app
from tests.factories import make_analysis_result
from tests.test_pdf import build_pdf, build_text_pdf


class ServiceBehavior(Protocol):
    async def __call__(self, pdf: ValidatedPdf) -> AnalysisResult: ...


class FakeService:
    def __init__(self, behavior: ServiceBehavior) -> None:
        self.behavior = behavior
        self.received: list[ValidatedPdf] = []
        self.closed = False

    async def analyze(self, pdf: ValidatedPdf) -> AnalysisResult:
        self.received.append(pdf)
        return await self.behavior(pdf)

    async def close(self) -> None:
        self.closed = True


async def successful(_: ValidatedPdf) -> AnalysisResult:
    return make_analysis_result()


@pytest.mark.anyio
async def test_valid_pdf_returns_analysis_and_closes_service() -> None:
    service = FakeService(successful)
    app = create_app(Settings(_env_file=None), analysis_service=service)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        response = await client.post(
            "/v1/resume-analyses",
            files={"file": ("resume.pdf", build_text_pdf(), "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["result"]["overall_score"] == 100.0
    assert len(service.received) == 1
    assert service.closed is True


@pytest.mark.anyio
async def test_non_pdf_returns_problem_details_without_calling_service() -> None:
    service = FakeService(successful)
    app = create_app(Settings(_env_file=None), analysis_service=service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/resume-analyses",
            files={"file": ("resume.txt", b"text", "text/plain")},
        )

    assert response.status_code == 415
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "unsupported_pdf"
    assert service.received == []


@pytest.mark.anyio
async def test_image_only_pdf_returns_422_without_calling_service() -> None:
    service = FakeService(successful)
    app = create_app(Settings(_env_file=None), analysis_service=service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/resume-analyses",
            files={"file": ("resume.pdf", build_pdf(), "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "pdf_text_unavailable"
    assert service.received == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ProviderTimeoutError("secret upstream detail A"), 504, "provider_timeout"),
        (ProviderOutputError("secret upstream detail B"), 502, "provider_invalid_output"),
    ],
)
async def test_provider_errors_are_safe_problem_details(
    error: Exception,
    status: int,
    code: str,
) -> None:
    async def failing(_: ValidatedPdf) -> AnalysisResult:
        raise error

    app = create_app(
        Settings(_env_file=None),
        analysis_service=FakeService(failing),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/resume-analyses",
            files={"file": ("resume.pdf", build_text_pdf(), "application/pdf")},
        )

    assert response.status_code == status
    assert response.json()["code"] == code
    assert "secret upstream detail" not in response.text


@pytest.mark.anyio
async def test_missing_api_key_is_safe_configuration_error() -> None:
    app = create_app(Settings(_env_file=None))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/resume-analyses",
            files={"file": ("resume.pdf", build_text_pdf(), "application/pdf")},
        )

    assert response.status_code == 500
    assert response.json()["code"] == "missing_api_key"
