from pathlib import Path

import pytest

from resume_matcher.domain.errors import RubricConfigurationError
from resume_matcher.domain.rubric import load_rubric


def test_fixed_rubric_contains_required_categories_and_total_weight() -> None:
    rubric = load_rubric(Path("config/ai_data_solution_rubric.yaml"))

    assert rubric.job_title == "AI & Data Solution"
    assert sum(criterion.weight for criterion in rubric.criteria) == 100
    assert {criterion.category.value for criterion in rubric.criteria} == {
        "experience",
        "skills",
        "knowledge",
        "tools",
        "education",
    }


def test_rubric_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "rubric.yaml"
    path.write_text(
        """
job_title: AI & Data Solution
jd_version: "1.0"
rubric_version: "1.0"
criteria:
  - id: duplicate
    name: First
    description: First
    category: skills
    weight: 50
  - id: duplicate
    name: Second
    description: Second
    category: tools
    weight: 50
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RubricConfigurationError, match="criterion identifiers must be unique"):
        load_rubric(path)
