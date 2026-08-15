from decimal import Decimal

import pytest

from resume_matcher.domain.errors import AssessmentValidationError
from resume_matcher.domain.models import CriterionAssessment, MatchBand, MatchingResult
from resume_matcher.domain.scoring import band_for_score, score_analysis
from tests.factories import make_catalog, make_matching, make_rubric


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (Decimal("85.00"), MatchBand.STRONG_MATCH),
        (Decimal("84.75"), MatchBand.MATCH),
        (Decimal("70.00"), MatchBand.MATCH),
        (Decimal("69.75"), MatchBand.PARTIAL_MATCH),
        (Decimal("50.00"), MatchBand.PARTIAL_MATCH),
        (Decimal("49.75"), MatchBand.LOW_MATCH),
    ],
)
def test_match_band_boundaries(score: Decimal, expected: MatchBand) -> None:
    assert band_for_score(score) is expected


def test_all_level_four_assessments_score_exactly_one_hundred() -> None:
    rubric = make_rubric()

    scored = score_analysis(make_catalog(), rubric, make_matching(rubric, level=4))

    assert scored.overall_score == Decimal("100.00")
    assert scored.match_band is MatchBand.STRONG_MATCH
    assert sum(Decimal(str(item.score)) for item in scored.category_scores) == Decimal("100.00")


def test_all_level_zero_assessments_score_zero() -> None:
    rubric = make_rubric()

    scored = score_analysis(make_catalog(), rubric, make_matching(rubric, level=0))

    assert scored.overall_score == Decimal("0.00")
    assert scored.match_band is MatchBand.LOW_MATCH
    assert all(not category.strengths for category in scored.category_scores)


def test_level_three_python_criterion_scores_six_points() -> None:
    rubric = make_rubric()
    matching = make_matching(rubric, level=0)
    python_assessment = next(
        item for item in matching.assessments if item.criterion_id == "skills.python"
    )
    python_assessment.evidence_level = 3
    python_assessment.evidence_ids = ["p1-e001"]

    scored = score_analysis(make_catalog(), rubric, matching)
    criterion = next(
        item
        for category in scored.category_scores
        for item in category.criteria
        if item.criterion_id == "skills.python"
    )

    assert criterion.score == 6.0


def test_missing_assessment_is_rejected() -> None:
    rubric = make_rubric()
    matching = make_matching(rubric)
    incomplete = MatchingResult(assessments=matching.assessments[:-1])

    with pytest.raises(AssessmentValidationError, match="missing criteria"):
        score_analysis(make_catalog(), rubric, incomplete)


def test_unknown_evidence_reference_is_rejected() -> None:
    rubric = make_rubric()
    matching = make_matching(rubric)
    first = matching.assessments[0]
    first.evidence_ids = ["unknown"]

    with pytest.raises(AssessmentValidationError, match="unknown evidence"):
        score_analysis(make_catalog(), rubric, matching)


def test_duplicate_criterion_assessment_is_rejected() -> None:
    rubric = make_rubric()
    matching = make_matching(rubric)
    duplicate = CriterionAssessment.model_validate(matching.assessments[0])
    invalid = MatchingResult(assessments=[*matching.assessments, duplicate])

    with pytest.raises(AssessmentValidationError, match="duplicate criteria"):
        score_analysis(make_catalog(), rubric, invalid)
