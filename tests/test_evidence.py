from resume_matcher.domain.models import SourceSection
from resume_matcher.services.evidence import build_evidence_catalog


def test_builder_creates_stable_page_ordered_chunks() -> None:
    page_texts = (
        "Experience\n• Built a Python API\ncontinued safely",
        "Technical Skills\nDocker",
    )

    first = build_evidence_catalog(page_texts)
    second = build_evidence_catalog(page_texts)

    assert first == second
    assert [item.id for item in first.items] == [
        "p1-e001",
        "p1-e002",
        "p2-e001",
        "p2-e002",
    ]
    assert first.items[1].quote == "• Built a Python API continued safely"
    assert first.items[1].source_section is SourceSection.EXPERIENCE
    assert first.items[3].source_section is SourceSection.SKILLS


def test_builder_excludes_contact_header_without_dropping_resume_content() -> None:
    page_texts = (
        "Candidate Name\n"
        "Bangkok | 080-000-0000 | candidate@example.com | linkedin.com/in/candidate\n"
        "Education\nBachelor of Science in Computer Science",
    )

    catalog = build_evidence_catalog(page_texts)

    quotes = [item.quote for item in catalog.items]
    assert "Candidate Name" in quotes
    assert "Bachelor of Science in Computer Science" in quotes
    assert not any("candidate@example.com" in quote for quote in quotes)
    assert not any("080-000-0000" in quote for quote in quotes)


def test_builder_splits_oversized_blocks_without_changing_word_order() -> None:
    source = " ".join(f"word{index}" for index in range(180))

    catalog = build_evidence_catalog((source,))

    assert len(catalog.items) > 1
    assert all(len(item.quote) <= 1000 for item in catalog.items)
    assert " ".join(item.quote for item in catalog.items) == source
