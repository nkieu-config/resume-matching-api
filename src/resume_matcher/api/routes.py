import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, File, Request, UploadFile

from resume_matcher.config import Settings
from resume_matcher.domain.errors import MissingApiKeyError, ProviderTimeoutError
from resume_matcher.domain.models import AnalysisResult
from resume_matcher.domain.rubric import load_rubric
from resume_matcher.providers.gemini import GeminiResumeAnalyzer
from resume_matcher.services.analyzer import AnalysisRunner, AnalysisService
from resume_matcher.services.pdf import validate_pdf

router = APIRouter()


def get_analysis_service(request: Request) -> AnalysisRunner:
    existing = request.app.state.analysis_service
    if existing is not None:
        return cast(AnalysisRunner, existing)
    settings = cast(Settings, request.app.state.settings)
    if settings.gemini_api_key is None:
        raise MissingApiKeyError("GEMINI_API_KEY is required")
    rubric = load_rubric(settings.rubric_path)
    service = AnalysisService(
        provider=GeminiResumeAnalyzer(settings),
        rubric=rubric,
        settings=settings,
    )
    request.app.state.analysis_service = service
    return service


@router.get("/health", tags=["system"])
async def health(request: Request) -> dict[str, str]:
    settings = cast(Settings, request.app.state.settings)
    return {"status": "ok", "version": settings.app_version}


@router.post(
    "/v1/resume-analyses",
    response_model=AnalysisResult,
    tags=["analysis"],
)
async def analyze_resume(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> AnalysisResult:
    settings = cast(Settings, request.app.state.settings)
    pdf = await validate_pdf(file, settings)
    service = get_analysis_service(request)
    try:
        async with asyncio.timeout(settings.overall_timeout_seconds):
            return await service.analyze(pdf)
    except TimeoutError as exc:
        raise ProviderTimeoutError("overall analysis deadline exceeded") from exc
