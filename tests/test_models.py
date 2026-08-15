import pytest
from pydantic import ValidationError

from resume_matcher.domain.models import (
    CriterionAssessment,
    EvidenceCatalog,
    EvidenceChunk,
    SourceSection,
)


def test_evidence_catalog_requires_unique_identifiers() -> None:
    evidence = EvidenceChunk(
        id="p1-e001",
        quote="Built a Python API",
        page=1,
        source_section=SourceSection.PROJECTS,
    )

    with pytest.raises(ValidationError, match="evidence identifiers must be unique"):
        EvidenceCatalog(items=[evidence, evidence])


@pytest.mark.parametrize(
    ("level", "evidence_ids"),
    [(0, ["p1-e001"]), (1, [])],
)
def test_criterion_assessment_enforces_evidence_consistency(
    level: int,
    evidence_ids: list[str],
) -> None:
    with pytest.raises(ValidationError, match="evidence"):
        CriterionAssessment(
            criterion_id="skills.python",
            evidence_level=level,
            evidence_ids=evidence_ids,
            rationale_th="เหตุผล",
        )
