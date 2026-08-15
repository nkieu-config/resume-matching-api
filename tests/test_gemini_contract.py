import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from resume_matcher.config import Settings
from resume_matcher.domain.errors import (
    ProviderAuthenticationError,
    ProviderOutputError,
    ProviderTimeoutError,
    ProviderTransientError,
)
from resume_matcher.domain.models import MatchingResult
from resume_matcher.providers.gemini import GeminiResumeAnalyzer
from tests.factories import make_catalog, make_rubric


class FakeInteractions:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return await response()
        return response


class FakeAsyncClient:
    def __init__(self, interactions: FakeInteractions) -> None:
        self.interactions = interactions

    async def aclose(self) -> None:
        return None


class FakeClient:
    def __init__(self, interactions: FakeInteractions) -> None:
        self.aio = FakeAsyncClient(interactions)


class ApiFailure(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"API failure {code}")


class SdkRateLimitFailure(Exception):
    status_code = 429


def matching_payload() -> dict[str, Any]:
    rubric = make_rubric()
    return {
        "assessments": [
            {
                "criterion_id": criterion.id,
                "evidence_level": 0,
                "evidence_ids": [],
                "rationale_th": "ไม่พบหลักฐาน",
                "gap_th": "ควรตรวจสอบเพิ่มเติม",
            }
            for criterion in rubric.criteria
        ]
    }


def interaction(output: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        output_text=json.dumps(output),
        usage=SimpleNamespace(total_input_tokens=20, total_output_tokens=10),
    )


def test_default_client_disables_sdk_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def make_client(**kwargs: Any) -> FakeClient:
        captured.update(kwargs)
        return FakeClient(FakeInteractions([]))

    monkeypatch.setattr("resume_matcher.providers.gemini.genai.Client", make_client)

    GeminiResumeAnalyzer(Settings(gemini_api_key="secret", _env_file=None))

    assert captured == {
        "api_key": "secret",
        "http_options": {"retry_options": {"attempts": 1}},
    }


@pytest.mark.anyio
async def test_match_sends_catalog_and_rubric_without_pdf() -> None:
    interactions = FakeInteractions([interaction(matching_payload())])
    analyzer = GeminiResumeAnalyzer(
        Settings(gemini_api_key="secret", _env_file=None),
        client=FakeClient(interactions),
    )

    output = await analyzer.match(make_catalog(), make_rubric())

    call = interactions.calls[0]
    text = call["input"][0]["text"]
    assert isinstance(output.matching, MatchingResult)
    assert call["model"] == "gemini-3.5-flash-lite"
    assert call["input"] == [{"type": "text", "text": text}]
    assert "EvidenceCatalog" in text
    assert "RubricConfig" in text
    assert "Built and evaluated a Python LLM API" in text
    assert "JVBER" not in text
    assert call["response_format"]["schema"]["title"] == "MatchingResult"
    assert output.usage.input_tokens == 20
    assert output.usage.output_tokens == 10


@pytest.mark.anyio
async def test_invalid_structured_output_is_classified() -> None:
    interactions = FakeInteractions([SimpleNamespace(output_text="not-json")])
    analyzer = GeminiResumeAnalyzer(
        Settings(gemini_api_key="secret", _env_file=None),
        client=FakeClient(interactions),
    )

    with pytest.raises(ProviderOutputError):
        await analyzer.match(make_catalog(), make_rubric())


@pytest.mark.anyio
async def test_authentication_failure_is_not_retried() -> None:
    interactions = FakeInteractions([ApiFailure(401)])
    analyzer = GeminiResumeAnalyzer(
        Settings(gemini_api_key="secret", _env_file=None),
        client=FakeClient(interactions),
    )

    with pytest.raises(ProviderAuthenticationError):
        await analyzer.match(make_catalog(), make_rubric())

    assert len(interactions.calls) == 1


@pytest.mark.anyio
async def test_transient_failure_retries_then_succeeds() -> None:
    interactions = FakeInteractions(
        [ApiFailure(503), ApiFailure(503), interaction(matching_payload())]
    )

    async def no_sleep(_: float) -> None:
        return None

    analyzer = GeminiResumeAnalyzer(
        Settings(gemini_api_key="secret", _env_file=None),
        client=FakeClient(interactions),
        sleep=no_sleep,
    )

    await analyzer.match(make_catalog(), make_rubric())

    assert len(interactions.calls) == 3


@pytest.mark.anyio
async def test_sdk_rate_limit_fails_fast_as_transient() -> None:
    interactions = FakeInteractions([SdkRateLimitFailure(), interaction(matching_payload())])

    async def no_sleep(_: float) -> None:
        return None

    analyzer = GeminiResumeAnalyzer(
        Settings(gemini_api_key="secret", _env_file=None),
        client=FakeClient(interactions),
        sleep=no_sleep,
    )

    with pytest.raises(ProviderTransientError):
        await analyzer.match(make_catalog(), make_rubric())

    assert len(interactions.calls) == 1


@pytest.mark.anyio
async def test_provider_timeout_is_classified() -> None:
    async def slow_response() -> SimpleNamespace:
        await asyncio.sleep(0.05)
        return interaction({})

    interactions = FakeInteractions([slow_response])
    analyzer = GeminiResumeAnalyzer(
        Settings(
            gemini_api_key="secret",
            provider_timeout_seconds=0.001,
            _env_file=None,
        ),
        client=FakeClient(interactions),
    )

    with pytest.raises(ProviderTimeoutError):
        await analyzer.match(make_catalog(), make_rubric())
