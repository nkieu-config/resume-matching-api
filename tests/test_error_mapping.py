from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from resume_matcher.config import Settings
from resume_matcher.domain.errors import (
    AssessmentValidationError,
    PdfTextUnavailableError,
    ProviderAuthenticationError,
    ProviderTransientError,
    RubricConfigurationError,
)
from resume_matcher.domain.models import AnalysisResult, ValidatedPdf
from resume_matcher.main import create_app
from tests.test_api import FakeService
from tests.test_pdf import build_text_pdf


@pytest.fixture
async def client_for_error(request: pytest.FixtureRequest) -> AsyncIterator[AsyncClient]:
    error = request.param

    async def failing(_: ValidatedPdf) -> AnalysisResult:
        raise error

    app = create_app(
        Settings(_env_file=None),
        analysis_service=FakeService(failing),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("client_for_error", "status", "code"),
    [
        (
            ProviderAuthenticationError("secret provider detail"),
            502,
            "provider_authentication_failed",
        ),
        (
            ProviderTransientError("secret provider detail"),
            502,
            "provider_temporarily_unavailable",
        ),
        (
            AssessmentValidationError("secret assessment detail"),
            502,
            "invalid_assessment",
        ),
        (
            RubricConfigurationError("secret rubric detail"),
            500,
            "invalid_rubric",
        ),
        (
            PdfTextUnavailableError("secret text detail"),
            422,
            "pdf_text_unavailable",
        ),
        (RuntimeError("secret unexpected detail"), 500, "internal_error"),
    ],
    indirect=["client_for_error"],
)
async def test_service_errors_have_safe_public_responses(
    client_for_error: AsyncClient,
    status: int,
    code: str,
) -> None:
    response = await client_for_error.post(
        "/v1/resume-analyses",
        files={"file": ("resume.pdf", build_text_pdf(), "application/pdf")},
    )

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code
    assert "secret" not in response.text
