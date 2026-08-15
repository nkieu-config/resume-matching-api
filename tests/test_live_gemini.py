import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from resume_matcher.config import Settings
from resume_matcher.domain.rubric import load_rubric
from resume_matcher.providers.gemini import GeminiResumeAnalyzer
from resume_matcher.services.analyzer import AnalysisService
from resume_matcher.services.pdf import validate_pdf

EXPECTATIONS = json.loads(Path("tests/eval_expectations.json").read_text(encoding="utf-8"))


@pytest.mark.integration
@pytest.mark.evaluation
@pytest.mark.anyio
@pytest.mark.parametrize(
    "expectation",
    EXPECTATIONS,
    ids=[item["file"] for item in EXPECTATIONS],
)
async def test_live_resume_evaluation(expectation: dict[str, object]) -> None:
    settings = Settings()
    if settings.gemini_api_key is None:
        pytest.skip("GEMINI_API_KEY is not configured")
    path = Path("tests/fixtures") / str(expectation["file"])
    upload = UploadFile(
        file=BytesIO(path.read_bytes()),
        filename=path.name,
        headers=Headers({"content-type": "application/pdf"}),
    )
    pdf = await validate_pdf(upload, settings)
    service = AnalysisService(
        GeminiResumeAnalyzer(settings),
        load_rubric(Path("config/ai_data_solution_rubric.yaml")),
        settings,
    )

    try:
        result = await service.analyze(pdf)
    finally:
        await service.close()

    assert result.result.match_band.value == expectation["expected_band"]
    criteria = {
        criterion.criterion_id: criterion
        for category in result.category_scores
        for criterion in category.criteria
    }
    for expected in expectation["expected_evidence"]:
        criterion = criteria[expected["criterion_id"]]
        quotes = [evidence.quote.casefold() for evidence in criterion.evidence]
        assert criterion.evidence_level > 0
        assert any(marker.casefold() in quote for marker in expected["markers"] for quote in quotes)
    for criterion_id in expectation["expected_zero"]:
        assert criteria[criterion_id].evidence_level == 0
    assert all(
        criterion.evidence
        for category in result.category_scores
        for criterion in category.criteria
        if criterion.evidence_level > 0
    )
    assert "HIRE" not in result.model_dump_json()
