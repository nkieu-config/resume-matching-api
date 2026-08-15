from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from resume_matcher.api.errors import register_error_handlers
from resume_matcher.api.routes import router
from resume_matcher.config import Settings, get_settings
from resume_matcher.services.analyzer import AnalysisRunner


def create_app(
    settings: Settings | None = None,
    analysis_service: AnalysisRunner | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        service = application.state.analysis_service
        if service is not None:
            await service.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.analysis_service = analysis_service
    register_error_handlers(application)
    application.include_router(router)

    return application


app = create_app()
