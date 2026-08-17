import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel

from resume_matcher.config import Settings
from resume_matcher.domain.errors import (
    MissingApiKeyError,
    ProviderAuthenticationError,
    ProviderOutputError,
    ProviderTimeoutError,
    ProviderTransientError,
)
from resume_matcher.domain.models import (
    EvidenceCatalog,
    MatchingResult,
    RubricConfig,
)
from resume_matcher.observability import log_event
from resume_matcher.providers.base import (
    MatchingOutput,
    ProviderUsage,
    load_prompt,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
Sleep = Callable[[float], Awaitable[None]]


class GeminiResumeAnalyzer:
    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if settings.gemini_api_key is None:
            raise MissingApiKeyError("GEMINI_API_KEY is required for resume analysis")
        self._settings = settings
        self._client = client or genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options={"retry_options": {"attempts": 1}},
        )
        self._sleep = sleep

    async def match(
        self,
        catalog: EvidenceCatalog,
        rubric: RubricConfig,
        validation_feedback: str | None = None,
    ) -> MatchingOutput:
        prompt = self._prompt_with_feedback(load_prompt("matching.md"), validation_feedback)
        context = (
            f"{prompt}\n\nEvidenceCatalog:\n{catalog.model_dump_json()}\n\n"
            f"RubricConfig:\n{rubric.model_dump_json()}"
        )
        model, usage = await self._structured_interaction(
            input_data=[{"type": "text", "text": context}],
            schema=MatchingResult,
        )
        return MatchingOutput(matching=model, usage=usage)

    async def close(self) -> None:
        await self._client.aio.aclose()

    async def _structured_interaction(
        self,
        input_data: list[dict[str, Any]],
        schema: type[ModelT],
    ) -> tuple[ModelT, ProviderUsage]:
        response = await self._request_with_retry(
            input_data=input_data,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema.model_json_schema(),
            },
        )
        try:
            raw_text = response.output_text
            raw_obj = json.loads(raw_text)
            if (
                isinstance(raw_obj, dict)
                and "assessments" in raw_obj
                and isinstance(raw_obj["assessments"], list)
            ):
                for item in raw_obj["assessments"]:
                    if (
                        isinstance(item, dict)
                        and item.get("evidence_level") == 0
                        and item.get("evidence_ids")
                    ):
                        item["evidence_ids"] = []
                parsed = schema.model_validate(raw_obj)
            else:
                parsed = schema.model_validate_json(raw_text)
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderOutputError(
                f"Gemini response did not match the required schema: {exc}"
            ) from exc
        usage_data = getattr(response, "usage", None)
        usage = ProviderUsage(
            input_tokens=getattr(usage_data, "total_input_tokens", None),
            output_tokens=getattr(usage_data, "total_output_tokens", None),
        )
        return parsed, usage

    async def _request_with_retry(
        self,
        input_data: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> Any:
        gen_config: dict[str, Any] = {"temperature": self._settings.gemini_temperature}
        if self._settings.gemini_seed is not None:
            gen_config["seed"] = self._settings.gemini_seed

        for attempt in range(3):
            try:
                async with asyncio.timeout(self._settings.provider_timeout_seconds):
                    return await self._client.aio.interactions.create(
                        model=self._settings.gemini_model,
                        input=input_data,
                        response_format=response_format,
                        generation_config=gen_config,
                    )
            except TimeoutError as exc:
                raise ProviderTimeoutError("Gemini request timed out") from exc
            except Exception as exc:
                status = self._status_code(exc)
                if status in {401, 403}:
                    raise ProviderAuthenticationError(
                        "Gemini authentication or permission failed"
                    ) from exc
                if status == 429:
                    raise ProviderTransientError("Gemini rate limit was reached") from exc
                if status not in {408, 500, 502, 503, 504}:
                    raise ProviderOutputError("Gemini request failed") from exc
                if attempt == 2:
                    raise ProviderTransientError(
                        "Gemini remained unavailable after retries"
                    ) from exc
                log_event(
                    "provider_retry",
                    model=self._settings.gemini_model,
                    attempt=attempt + 2,
                    status=status,
                )
                await self._sleep(0.1 * (2**attempt))
        raise ProviderTransientError("Gemini remained unavailable after retries")

    @staticmethod
    def _prompt_with_feedback(prompt: str, feedback: str | None) -> str:
        if feedback is None:
            return prompt
        return f"{prompt}\n\nValidation feedback from the previous attempt:\n{feedback}"

    @staticmethod
    def _status_code(exc: Exception) -> int:
        response = getattr(exc, "response", None)
        candidates = (
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
            getattr(response, "status_code", None),
        )
        for candidate in candidates:
            if isinstance(candidate, int):
                return candidate
        return 0
