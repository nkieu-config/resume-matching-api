from dataclasses import dataclass
from decimal import Decimal

from resume_matcher.domain.errors import AssessmentValidationError
from resume_matcher.domain.models import (
    Category,
    CategoryScore,
    CriterionScore,
    EvidenceCatalog,
    MatchBand,
    MatchingResult,
    RubricConfig,
)


@dataclass(frozen=True, slots=True)
class ScoredAnalysis:
    overall_score: Decimal
    match_band: MatchBand
    category_scores: tuple[CategoryScore, ...]


def band_for_score(score: Decimal) -> MatchBand:
    if score >= Decimal("85.00"):
        return MatchBand.STRONG_MATCH
    if score >= Decimal("70.00"):
        return MatchBand.MATCH
    if score >= Decimal("50.00"):
        return MatchBand.PARTIAL_MATCH
    return MatchBand.LOW_MATCH


def validate_matching_result(
    catalog: EvidenceCatalog,
    rubric: RubricConfig,
    matching: MatchingResult,
) -> None:
    expected = {criterion.id for criterion in rubric.criteria}
    actual_ids = [assessment.criterion_id for assessment in matching.assessments]
    actual = set(actual_ids)
    if len(actual_ids) != len(actual):
        raise AssessmentValidationError("duplicate criteria in matching result")
    missing = sorted(expected - actual)
    if missing:
        raise AssessmentValidationError(f"missing criteria: {', '.join(missing)}")
    unknown = sorted(actual - expected)
    if unknown:
        raise AssessmentValidationError(f"unknown criteria: {', '.join(unknown)}")
    known_evidence = {evidence.id for evidence in catalog.items}
    for assessment in matching.assessments:
        invalid = sorted(set(assessment.evidence_ids) - known_evidence)
        if invalid:
            raise AssessmentValidationError(
                f"unknown evidence for {assessment.criterion_id}: {', '.join(invalid)}"
            )


def score_analysis(
    catalog: EvidenceCatalog,
    rubric: RubricConfig,
    matching: MatchingResult,
) -> ScoredAnalysis:
    validate_matching_result(catalog, rubric, matching)
    assessment_by_id = {assessment.criterion_id: assessment for assessment in matching.assessments}
    evidence_by_id = {evidence.id: evidence for evidence in catalog.items}
    category_scores: list[CategoryScore] = []
    overall = Decimal("0.00")

    for category in Category:
        criteria = [criterion for criterion in rubric.criteria if criterion.category is category]
        criterion_scores: list[CriterionScore] = []
        category_total = Decimal("0.00")
        strengths: list[str] = []
        gaps: list[str] = []
        for criterion in criteria:
            assessment = assessment_by_id[criterion.id]
            score = Decimal(criterion.weight) * Decimal(assessment.evidence_level) / Decimal(4)
            category_total += score
            criterion_scores.append(
                CriterionScore(
                    criterion_id=criterion.id,
                    criterion_name=criterion.name,
                    category=criterion.category,
                    score=float(score),
                    max_score=criterion.weight,
                    evidence_level=assessment.evidence_level,
                    rationale_th=assessment.rationale_th,
                    gap_th=assessment.gap_th,
                    evidence=[evidence_by_id[item] for item in assessment.evidence_ids],
                )
            )
            if assessment.evidence_level >= 3:
                strengths.append(criterion.name)
            if assessment.evidence_level <= 1:
                gaps.append(criterion.name)
        overall += category_total
        category_scores.append(
            CategoryScore(
                category=category,
                score=float(category_total),
                max_score=sum(criterion.weight for criterion in criteria),
                strengths=strengths,
                gaps=gaps,
                criteria=criterion_scores,
            )
        )

    return ScoredAnalysis(
        overall_score=overall.quantize(Decimal("0.00")),
        match_band=band_for_score(overall),
        category_scores=tuple(category_scores),
    )
