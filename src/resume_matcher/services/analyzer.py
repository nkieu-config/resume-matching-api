import time
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from resume_matcher.config import Settings
from resume_matcher.domain.errors import AssessmentValidationError, ProviderOutputError
from resume_matcher.domain.models import (
    AnalysisMetadata,
    AnalysisResult,
    CategoryScore,
    EvidenceCatalog,
    JobInfo,
    MatchBand,
    ResultSummary,
    RubricConfig,
    ValidatedPdf,
)
from resume_matcher.domain.scoring import score_analysis, validate_matching_result
from resume_matcher.observability import log_event
from resume_matcher.providers.base import (
    MatchingOutput,
    ResumeAnalysisProvider,
)
from resume_matcher.services.evidence import build_evidence_catalog

Clock = Callable[[], float]
IdFactory = Callable[[], str]


class AnalysisRunner(Protocol):
    async def analyze(self, pdf: ValidatedPdf) -> AnalysisResult: ...

    async def close(self) -> None: ...


class AnalysisService:
    def __init__(
        self,
        provider: ResumeAnalysisProvider,
        rubric: RubricConfig,
        settings: Settings,
        clock: Clock = time.perf_counter,
        id_factory: IdFactory = lambda: uuid4().hex,
    ) -> None:
        self._provider = provider
        self._rubric = rubric
        self._settings = settings
        self._clock = clock
        self._id_factory = id_factory

    async def analyze(self, pdf: ValidatedPdf) -> AnalysisResult:
        started = self._clock()
        catalog = build_evidence_catalog(pdf.page_texts)
        matching, request_count = await self._match(catalog)
        scored = score_analysis(catalog, self._rubric, matching.matching)
        elapsed_ms = round((self._clock() - started) * 1000)
        input_tokens = matching.usage.input_tokens
        output_tokens = matching.usage.output_tokens
        analysis_id = self._id_factory()
        log_event(
            "analysis_completed",
            analysis_id=analysis_id,
            model=self._settings.gemini_model,
            page_count=pdf.page_count,
            pdf_bytes=len(pdf.data),
            processing_time_ms=elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return AnalysisResult(
            analysis_id=analysis_id,
            job=JobInfo(
                title=self._rubric.job_title,
                jd_version=self._rubric.jd_version,
            ),
            result=ResultSummary(
                overall_score=float(scored.overall_score),
                match_band=scored.match_band,
                summary=self._summary(scored.match_band, scored.category_scores),
            ),
            category_scores=list(scored.category_scores),
            metadata=AnalysisMetadata(
                model=self._settings.gemini_model,
                evidence_catalog_version=catalog.version,
                matching_prompt_version="2.3",
                rubric_version=self._rubric.rubric_version,
                processing_time_ms=elapsed_ms,
                llm_request_count=request_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            decision_support_notice=("ผลลัพธ์นี้เป็นเครื่องมือช่วยประเมินและควรได้รับการทบทวนโดยมนุษย์"),
        )

    async def close(self) -> None:
        await self._provider.close()

    async def _match(self, catalog: EvidenceCatalog) -> tuple[MatchingOutput, int]:
        feedback = (
            "Return exactly one schema-valid assessment for every rubric criterion "
            "using only known evidence identifiers."
        )
        try:
            first = await self._provider.match(catalog, self._rubric)
        except ProviderOutputError:
            second = await self._provider.match(
                catalog,
                self._rubric,
                feedback,
            )
        else:
            try:
                validate_matching_result(catalog, self._rubric, first.matching)
                return first, 1
            except AssessmentValidationError:
                second = await self._provider.match(
                    catalog,
                    self._rubric,
                    feedback,
                )
        try:
            validate_matching_result(catalog, self._rubric, second.matching)
        except AssessmentValidationError as exc:
            raise ProviderOutputError("matching validation failed twice") from exc
        return second, 2

    @staticmethod
    def _summary(
        band: MatchBand,
        category_scores: tuple[CategoryScore, ...],
    ) -> str:
        ordered = sorted(
            category_scores,
            key=lambda item: item.score / item.max_score,
            reverse=True,
        )
        strongest = ordered[0].category.value
        gaps = [gap for category in ordered for gap in category.gaps][:3]
        gap_text = ", ".join(gaps) if gaps else "ไม่พบช่องว่างหลักจากข้อมูลใน Resume"
        return (
            f"ผลการจับคู่อยู่ในระดับ {band.value} โดยหมวดที่เด่นที่สุดคือ {strongest} "
            f"และประเด็นที่ควรตรวจสอบเพิ่มเติมคือ {gap_text}"
        )
