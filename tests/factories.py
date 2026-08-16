from pathlib import Path

from resume_matcher.domain.models import (
    AnalysisMetadata,
    AnalysisResult,
    CriterionAssessment,
    EvidenceCatalog,
    EvidenceChunk,
    JobInfo,
    MatchBand,
    MatchingResult,
    ResultSummary,
    RubricConfig,
    SourceSection,
)
from resume_matcher.domain.rubric import load_rubric


def make_rubric() -> RubricConfig:
    return load_rubric(Path("config/ai_data_solution_rubric.yaml"))


def make_catalog() -> EvidenceCatalog:
    return EvidenceCatalog(
        items=[
            EvidenceChunk(
                id="p1-e001",
                quote="Built and evaluated a Python LLM API deployed with Docker",
                page=1,
                source_section=SourceSection.EXPERIENCE,
            )
        ]
    )


def make_matching(rubric: RubricConfig, level: int = 4) -> MatchingResult:
    return MatchingResult(
        assessments=[
            CriterionAssessment(
                criterion_id=criterion.id,
                evidence_level=level,
                evidence_ids=["p1-e001"] if level > 0 else [],
                rationale_th="พบหลักฐานที่สอดคล้อง",
                gap_th=None if level >= 2 else "ควรตรวจสอบประสบการณ์เพิ่มเติม",
            )
            for criterion in rubric.criteria
        ]
    )


def make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        analysis_id="analysis-test",
        job=JobInfo(title="AI & Data Solution", jd_version="1.0"),
        result=ResultSummary(
            overall_score=100.0,
            match_band=MatchBand.STRONG_MATCH,
            summary="ผู้สมัครมีหลักฐานครบถ้วน",
        ),
        category_scores=[],
        metadata=AnalysisMetadata(
            model="gemini-3.5-flash-lite",
            evidence_catalog_version="1.1",
            matching_prompt_version="2.3",
            rubric_version="1.0",
            processing_time_ms=100,
            llm_request_count=1,
        ),
        decision_support_notice=("ผลลัพธ์นี้เป็นเครื่องมือช่วยประเมินและควรได้รับการทบทวนโดยมนุษย์"),
    )
