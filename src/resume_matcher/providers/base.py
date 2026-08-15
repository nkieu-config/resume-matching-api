from dataclasses import dataclass
from importlib.resources import files
from typing import Protocol

from resume_matcher.domain.models import (
    EvidenceCatalog,
    MatchingResult,
    RubricConfig,
)


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class MatchingOutput:
    matching: MatchingResult
    usage: ProviderUsage


class ResumeAnalysisProvider(Protocol):
    async def match(
        self,
        catalog: EvidenceCatalog,
        rubric: RubricConfig,
        validation_feedback: str | None = None,
    ) -> MatchingOutput: ...

    async def close(self) -> None: ...


def load_prompt(name: str) -> str:
    return files("resume_matcher.prompts").joinpath(name).read_text(encoding="utf-8").strip()
