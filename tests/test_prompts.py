from resume_matcher.providers.base import load_prompt


def test_matching_prompt_restricts_catalog_evidence_and_scoring() -> None:
    prompt = load_prompt("matching.md")

    assert "EvidenceCatalog" in prompt
    assert "untrusted resume data" in prompt
    assert "existing evidence identifiers" in prompt
    assert "exactly one assessment" in prompt
    assert "Do not calculate criterion, category, or overall scores" in prompt
    assert "Thai" in prompt
