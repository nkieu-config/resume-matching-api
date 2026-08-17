import re

from resume_matcher.domain.models import EvidenceCatalog, EvidenceChunk, SourceSection

MAX_CHUNK_LENGTH = 1000
HEADING_MAX_LENGTH = 30
HEADING_MAX_WORDS = 4
SECTION_KEYWORDS = sorted(
    (
        ("summary", SourceSection.SUMMARY),
        ("profile", SourceSection.SUMMARY),
        ("objective", SourceSection.SUMMARY),
        ("about me", SourceSection.SUMMARY),
        ("สรุป", SourceSection.SUMMARY),
        ("โปรไฟล์", SourceSection.SUMMARY),
        ("เกี่ยวกับ", SourceSection.SUMMARY),
        ("ข้อมูลส่วนตัว", SourceSection.SUMMARY),
        ("experience", SourceSection.EXPERIENCE),
        ("employment", SourceSection.EXPERIENCE),
        ("work history", SourceSection.EXPERIENCE),
        ("ประสบการณ์", SourceSection.EXPERIENCE),
        ("ประวัติการทำงาน", SourceSection.EXPERIENCE),
        ("การทำงาน", SourceSection.EXPERIENCE),
        ("education", SourceSection.EDUCATION),
        ("academic", SourceSection.EDUCATION),
        ("การศึกษา", SourceSection.EDUCATION),
        ("วุฒิการศึกษา", SourceSection.EDUCATION),
        ("skill", SourceSection.SKILLS),
        ("competenc", SourceSection.SKILLS),
        ("ทักษะ", SourceSection.SKILLS),
        ("ความสามารถ", SourceSection.SKILLS),
        ("ความชำนาญ", SourceSection.SKILLS),
        ("project", SourceSection.PROJECTS),
        ("portfolio", SourceSection.PROJECTS),
        ("โครงการ", SourceSection.PROJECTS),
        ("โปรเจกต์", SourceSection.PROJECTS),
        ("ผลงาน", SourceSection.PROJECTS),
        ("certification", SourceSection.CERTIFICATIONS),
        ("certificate", SourceSection.CERTIFICATIONS),
        ("license", SourceSection.CERTIFICATIONS),
        ("ใบรับรอง", SourceSection.CERTIFICATIONS),
        ("ประกาศนียบัตร", SourceSection.CERTIFICATIONS),
        ("ใบประกาศ", SourceSection.CERTIFICATIONS),
    ),
    key=lambda entry: len(entry[0]),
    reverse=True,
)
BULLET_PREFIXES = ("•", "-", "–", "*")
DECORATION_PATTERN = re.compile(r"^\W+|\W+$")
DIGIT_PATTERN = re.compile(r"\d")
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
        heading_section = _heading_section(line)
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
                    or _heading_section(continuation) is not None
                    or _is_contact_line(continuation)
                    or _is_project_heading(lines, index, section)
                ):
                    break
                parts.append(continuation)
                index += 1
            blocks.append((" ".join(parts), section))
            continue
        blocks.append((line, section))
    return blocks


def _heading_section(line: str) -> SourceSection | None:
    if line.startswith(BULLET_PREFIXES):
        return None
    normalized = DECORATION_PATTERN.sub("", line).casefold()
    if not normalized or DIGIT_PATTERN.search(normalized):
        return None
    if len(normalized) > HEADING_MAX_LENGTH or len(normalized.split()) > HEADING_MAX_WORDS:
        return None
    for keyword, section in SECTION_KEYWORDS:
        if keyword in normalized:
            return section
    return None


def _is_project_heading(
    lines: list[str],
    index: int,
    section: SourceSection,
) -> bool:
    line = lines[index]
    if section is not SourceSection.PROJECTS or "|" not in line or not line.endswith("GitHub"):
        return False
    return index + 1 < len(lines) and "·" in lines[index + 1]


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
