import re

from resume_matcher.domain.models import EvidenceCatalog, EvidenceChunk, SourceSection

MAX_CHUNK_LENGTH = 1000
SECTION_HEADINGS = {
    "summary": SourceSection.SUMMARY,
    "profile": SourceSection.SUMMARY,
    "experience": SourceSection.EXPERIENCE,
    "work experience": SourceSection.EXPERIENCE,
    "education": SourceSection.EDUCATION,
    "skills": SourceSection.SKILLS,
    "technical skills": SourceSection.SKILLS,
    "projects": SourceSection.PROJECTS,
    "certifications": SourceSection.CERTIFICATIONS,
    "certificates": SourceSection.CERTIFICATIONS,
}
BULLET_PREFIXES = ("•", "-", "–", "*")
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
PROFILE_PATTERN = re.compile(r"(?:linkedin\.com|github\.com|gitlab\.com)", re.IGNORECASE)


def build_evidence_catalog(page_texts: tuple[str, ...]) -> EvidenceCatalog:
    items: list[EvidenceChunk] = []
    current_section = SourceSection.OTHER
    for page_number, page_text in enumerate(page_texts, start=1):
        page_items: list[EvidenceChunk] = []
        lines = [
            line.strip() for line in page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        for block, section in _blocks(lines, current_section):
            current_section = section
            for part in _split_block(block):
                page_items.append(
                    EvidenceChunk(
                        id=f"p{page_number}-e{len(page_items) + 1:03d}",
                        quote=part,
                        page=page_number,
                        source_section=current_section,
                    )
                )
        items.extend(page_items)
    return EvidenceCatalog(items=items)


def _blocks(
    lines: list[str],
    initial_section: SourceSection,
) -> list[tuple[str, SourceSection]]:
    blocks: list[tuple[str, SourceSection]] = []
    section = initial_section
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line or _is_contact_line(line):
            continue
        heading_section = SECTION_HEADINGS.get(line.casefold())
        if heading_section is not None:
            section = heading_section
            blocks.append((line, section))
            continue
        if line.startswith(BULLET_PREFIXES):
            parts = [line]
            while index < len(lines):
                continuation = lines[index]
                if (
                    not continuation
                    or continuation.startswith(BULLET_PREFIXES)
                    or SECTION_HEADINGS.get(continuation.casefold()) is not None
                    or _is_contact_line(continuation)
                ):
                    break
                parts.append(continuation)
                index += 1
            blocks.append((" ".join(parts), section))
            continue
        blocks.append((line, section))
    return blocks


def _is_contact_line(value: str) -> bool:
    return bool(
        EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value) or PROFILE_PATTERN.search(value)
    )


def _split_block(value: str) -> list[str]:
    if len(value) <= MAX_CHUNK_LENGTH:
        return [value]
    words = value.split()
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        added_length = len(word) if not current else len(word) + 1
        if current and current_length + added_length > MAX_CHUNK_LENGTH:
            chunks.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += added_length
    if current:
        chunks.append(" ".join(current))
    return chunks
