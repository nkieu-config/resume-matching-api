from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from resume_matcher.domain.errors import (
    AssessmentValidationError,
    InvalidPdfError,
    MissingApiKeyError,
    PdfTextUnavailableError,
    PdfTooLargeError,
    ProviderAuthenticationError,
    ProviderOutputError,
    ProviderTimeoutError,
    ProviderTransientError,
    ResumeMatcherError,
    RubricConfigurationError,
    UnsupportedPdfError,
)
from resume_matcher.observability import log_event


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    status: int
    title: str
    detail: str


ERRORS: dict[type[ResumeMatcherError], ErrorDefinition] = {
    UnsupportedPdfError: ErrorDefinition(415, "Unsupported PDF", "Upload one valid PDF file."),
    PdfTooLargeError: ErrorDefinition(413, "PDF too large", "The PDF exceeds 10 MB."),
    InvalidPdfError: ErrorDefinition(
        422,
        "Invalid PDF",
        "The PDF is corrupt, encrypted, empty, or exceeds 20 pages.",
    ),
    PdfTextUnavailableError: ErrorDefinition(
        422,
        "PDF text unavailable",
        "The PDF does not contain extractable resume text.",
    ),
    MissingApiKeyError: ErrorDefinition(
        500,
        "Service configuration error",
        "Resume analysis is not configured.",
    ),
    ProviderAuthenticationError: ErrorDefinition(
        502,
        "AI provider error",
        "The AI provider rejected the service credentials.",
    ),
    ProviderTransientError: ErrorDefinition(
        502,
        "AI provider unavailable",
        "The AI provider is temporarily unavailable.",
    ),
    ProviderOutputError: ErrorDefinition(
        502,
        "AI processing error",
        "The AI provider could not return a valid analysis.",
    ),
    ProviderTimeoutError: ErrorDefinition(
        504,
        "AI provider timeout",
        "The AI provider did not respond before the deadline.",
    ),
    AssessmentValidationError: ErrorDefinition(
        502,
        "AI processing error",
        "The AI assessment was inconsistent.",
    ),
    RubricConfigurationError: ErrorDefinition(
        500,
        "Service configuration error",
        "The scoring rubric is invalid.",
    ),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ResumeMatcherError)
    async def handle_domain_error(
        request: Request,
        error: ResumeMatcherError,
    ) -> JSONResponse:
        definition = ERRORS.get(
            type(error),
            ErrorDefinition(500, "Internal error", "The request could not be processed."),
        )
        problem = ProblemDetail(
            type=f"https://resume-matcher.local/problems/{error.code}",
            title=definition.title,
            status=definition.status,
            detail=definition.detail,
            code=error.code,
        )
        return JSONResponse(
            status_code=definition.status,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        log_event("request_failed", error_type=type(error).__name__)
        problem = ProblemDetail(
            type="https://resume-matcher.local/problems/internal_error",
            title="Internal error",
            status=500,
            detail="The request could not be processed.",
            code="internal_error",
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )
