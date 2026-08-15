from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Category(StrEnum):
    EXPERIENCE = "experience"
    SKILLS = "skills"
    KNOWLEDGE = "knowledge"
    TOOLS = "tools"
    EDUCATION = "education"


class SourceSection(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    OTHER = "other"


class MatchBand(StrEnum):
    STRONG_MATCH = "STRONG_MATCH"
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    LOW_MATCH = "LOW_MATCH"


class EvidenceChunk(StrictModel):
    id: str = Field(pattern=r"^p[1-9]\d*-e\d{3}$")
    quote: str = Field(min_length=1, max_length=1000)
    page: int = Field(ge=1)
    source_section: SourceSection


class EvidenceCatalog(StrictModel):
    version: str = "1.0"
    items: list[EvidenceChunk] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identifiers(self) -> "EvidenceCatalog":
        identifiers = [item.id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evidence identifiers must be unique")
        return self


class RubricCriterion(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: Category
    weight: int = Field(ge=1)
    preferred: bool = False


class RubricConfig(StrictModel):
    job_title: str
    jd_version: str
    rubric_version: str
    criteria: list[RubricCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rubric(self) -> "RubricConfig":
        identifiers = [criterion.id for criterion in self.criteria]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("criterion identifiers must be unique")
        total = sum(criterion.weight for criterion in self.criteria)
        if total != 100:
            raise ValueError(f"rubric weights must total 100, got {total}")
        return self


class CriterionAssessment(StrictModel):
    criterion_id: str
    evidence_level: int = Field(ge=0, le=4)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale_th: str = Field(min_length=1, max_length=1000)
    gap_th: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_level_evidence(self) -> "CriterionAssessment":
        if self.evidence_level == 0 and self.evidence_ids:
            raise ValueError("level zero must not contain evidence")
        if self.evidence_level > 0 and not self.evidence_ids:
            raise ValueError("positive evidence level requires evidence")
        return self


class MatchingResult(StrictModel):
    assessments: list[CriterionAssessment] = Field(min_length=1)


class CriterionScore(StrictModel):
    criterion_id: str
    criterion_name: str
    category: Category
    score: float = Field(ge=0)
    max_score: int = Field(ge=1)
    evidence_level: int = Field(ge=0, le=4)
    rationale_th: str
    gap_th: str | None = None
    evidence: list[EvidenceChunk]


class CategoryScore(StrictModel):
    category: Category
    score: float = Field(ge=0)
    max_score: int = Field(ge=1)
    strengths: list[str]
    gaps: list[str]
    criteria: list[CriterionScore]


class JobInfo(StrictModel):
    title: str
    jd_version: str


class ResultSummary(StrictModel):
    overall_score: float = Field(ge=0, le=100)
    match_band: MatchBand
    summary: str


class AnalysisMetadata(StrictModel):
    model: str
    evidence_catalog_version: str
    matching_prompt_version: str
    rubric_version: str
    analysis_language: str = "th"
    processing_time_ms: int = Field(ge=0)
    llm_request_count: int = Field(ge=1, le=2)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AnalysisResult(StrictModel):
    analysis_id: str
    job: JobInfo
    result: ResultSummary
    category_scores: list[CategoryScore]
    metadata: AnalysisMetadata
    decision_support_notice: str


@dataclass(frozen=True, slots=True)
class ValidatedPdf:
    data: bytes
    page_count: int
    filename: str
    page_texts: tuple[str, ...] = ()
