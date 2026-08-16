from collections.abc import Callable, Iterator

import pytest

from resume_matcher.config import Settings
from resume_matcher.domain.errors import ProviderOutputError
from resume_matcher.domain.models import EvidenceCatalog, MatchingResult, RubricConfig, ValidatedPdf
from resume_matcher.providers.base import MatchingOutput, ProviderUsage
from resume_matcher.services.analyzer import AnalysisService
from tests.factories import make_matching, make_rubric

MATCHING_CORRECTION = (
    "Return exactly one schema-valid assessment for every rubric criterion "
    "using only known evidence identifiers."
)


class FakeAnalyzer:
    def __init__(self, outputs: list[MatchingOutput | Exception]) -> None:
        self.outputs = outputs
        self.feedback: list[str | None] = []
        self.catalogs: list[EvidenceCatalog] = []
        self.closed = False

    async def match(
        self,
        catalog: EvidenceCatalog,
        rubric: RubricConfig,
        validation_feedback: str | None = None,
    ) -> MatchingOutput:
        self.catalogs.append(catalog)
        self.feedback.append(validation_feedback)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output

    async def close(self) -> None:
        self.closed = True


def clock(values: list[float]) -> Callable[[], float]:
    iterator: Iterator[float] = iter(values)
    return lambda: next(iterator)


def make_pdf() -> ValidatedPdf:
    return ValidatedPdf(
        b"%PDF-test",
        1,
        "resume.pdf",
        ("Experience\nBuilt and evaluated a Python LLM API deployed with Docker",),
    )


@pytest.mark.anyio
async def test_analysis_uses_one_matching_call_and_assembles_scores() -> None:
    rubric = make_rubric()
    matching = make_matching(rubric, 4)
    for assessment in matching.assessments:
        assessment.evidence_ids = ["p1-e002"]
    provider = FakeAnalyzer([MatchingOutput(matching, ProviderUsage(100, 40))])
    service = AnalysisService(
        provider=provider,
        rubric=rubric,
        settings=Settings(gemini_api_key="secret", _env_file=None),
        clock=clock([1.0, 1.125]),
        id_factory=lambda: "analysis-123",
    )

    result = await service.analyze(make_pdf())

    assert result.analysis_id == "analysis-123"
    assert result.result.overall_score == 100.0
    assert result.result.match_band == "STRONG_MATCH"
    assert "ระดับ STRONG_MATCH" in result.result.summary
    assert result.metadata.processing_time_ms == 125
    assert result.metadata.input_tokens == 100
    assert result.metadata.output_tokens == 40
    assert result.metadata.llm_request_count == 1
    assert result.metadata.evidence_catalog_version == "1.1"
    assert result.metadata.matching_prompt_version == "2.3"
    assert len(result.category_scores) == 5
    assert provider.feedback == [None]
    assert provider.catalogs[0].items[1].quote.startswith("Built and evaluated")


@pytest.mark.anyio
async def test_matching_schema_failure_gets_one_controlled_retry() -> None:
    rubric = make_rubric()
    provider = FakeAnalyzer(
        [
            ProviderOutputError("invalid matching schema"),
            MatchingOutput(make_matching(rubric), ProviderUsage()),
        ]
    )
    service = AnalysisService(
        provider,
        rubric,
        Settings(gemini_api_key="secret", _env_file=None),
    )

    result = await service.analyze(make_pdf())

    assert provider.feedback == [None, MATCHING_CORRECTION]
    assert result.metadata.llm_request_count == 2


@pytest.mark.anyio
async def test_matching_business_failure_gets_one_controlled_retry() -> None:
    rubric = make_rubric()
    invalid = MatchingResult(assessments=make_matching(rubric).assessments[:-1])
    provider = FakeAnalyzer(
        [
            MatchingOutput(invalid, ProviderUsage()),
            MatchingOutput(make_matching(rubric), ProviderUsage()),
        ]
    )
    service = AnalysisService(
        provider,
        rubric,
        Settings(gemini_api_key="secret", _env_file=None),
    )

    await service.analyze(make_pdf())

    assert provider.feedback == [None, MATCHING_CORRECTION]


@pytest.mark.anyio
async def test_second_matching_failure_becomes_provider_output_error() -> None:
    rubric = make_rubric()
    invalid = MatchingResult(assessments=make_matching(rubric).assessments[:-1])
    provider = FakeAnalyzer(
        [MatchingOutput(invalid, ProviderUsage()), MatchingOutput(invalid, ProviderUsage())]
    )
    service = AnalysisService(
        provider,
        rubric,
        Settings(gemini_api_key="secret", _env_file=None),
    )

    with pytest.raises(ProviderOutputError, match="matching validation failed twice"):
        await service.analyze(make_pdf())

    assert provider.feedback == [None, MATCHING_CORRECTION]


@pytest.mark.anyio
async def test_close_closes_provider() -> None:
    provider = FakeAnalyzer([])
    service = AnalysisService(
        provider,
        make_rubric(),
        Settings(gemini_api_key="secret", _env_file=None),
    )

    await service.close()

    assert provider.closed is True
