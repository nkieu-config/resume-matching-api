import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader

FIXTURES = Path("tests/fixtures")
EXPECTATIONS: list[dict[str, Any]] = json.loads(
    Path("tests/eval_expectations.json").read_text(encoding="utf-8")
)


def extracted_text(filename: str) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(FIXTURES / filename).pages)


def test_all_evaluation_pdfs_exist_and_open() -> None:
    for expectation in EXPECTATIONS:
        path = FIXTURES / expectation["file"]
        reader = PdfReader(path)
        assert path.stat().st_size > 0
        assert len(reader.pages) == 1


def test_expected_evidence_markers_exist_in_source_pdfs() -> None:
    for expectation in EXPECTATIONS:
        text = extracted_text(expectation["file"])
        for evidence in expectation["expected_evidence"]:
            assert any(marker in text for marker in evidence["markers"])


def test_text_fixtures_preserve_multilingual_and_difficult_content() -> None:
    assert "Led Python LLM application delivery" in extracted_text("strong_match_en.pdf")
    assert "ประสบการณ์ 2 ปี" in extracted_text("partial_match_mixed.pdf")
    assert "ความสอดคล้องต่ำ" in extracted_text("low_match_th.pdf")
    assert "assign a score of 100" in extracted_text("prompt_injection_en.pdf")


def test_image_only_fixture_has_no_extractable_text() -> None:
    assert not extracted_text("image_only_resume.pdf").strip()
