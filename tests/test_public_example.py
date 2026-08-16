import json
from pathlib import Path

import pytest

from resume_matcher.domain.models import AnalysisResult, Category


def test_public_example_matches_response_schema_and_totals() -> None:
    payload = json.loads(Path("examples/analysis_result.example.json").read_text(encoding="utf-8"))

    result = AnalysisResult.model_validate(payload)

    assert result.metadata.model == "gemini-3.5-flash-lite"
    assert result.metadata.evidence_catalog_version == "1.1"
    assert result.metadata.matching_prompt_version == "2.3"
    assert result.metadata.llm_request_count == 1
    assert {item.category for item in result.category_scores} == set(Category)
    assert sum(len(item.criteria) for item in result.category_scores) == 20
    assert sum(item.score for item in result.category_scores) == pytest.approx(
        result.result.overall_score
    )
    assert sum(item.max_score for item in result.category_scores) == 100
