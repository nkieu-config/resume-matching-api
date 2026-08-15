import json
import logging

import pytest

from resume_matcher.observability import log_event


def test_log_event_serializes_structured_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="resume_matcher"):
        log_event("provider_retry", model="gemini-test", attempt=2, status=503)

    payload = json.loads(caplog.records[0].message)
    assert payload == {
        "attempt": 2,
        "event": "provider_retry",
        "model": "gemini-test",
        "status": 503,
    }
