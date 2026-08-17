from pathlib import Path

import pytest

from resume_matcher.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Resume Matching API"
    assert settings.app_version == "0.1.0"
    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.max_pdf_bytes == 10 * 1024 * 1024
    assert settings.max_pdf_pages == 20
    assert settings.provider_timeout_seconds == 45.0
    assert settings.overall_timeout_seconds == 110.0


def test_rubric_path_resolves_without_depending_on_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.rubric_path.is_absolute()
    assert settings.rubric_path.is_file()
    assert settings.rubric_path.name == "ai_data_solution_rubric.yaml"


def test_settings_reads_rubric_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    override = tmp_path / "other_role.yaml"
    monkeypatch.setenv("RUBRIC_PATH", str(override))

    settings = Settings(_env_file=None)

    assert settings.rubric_path == override


def test_settings_reads_gemini_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = Settings(_env_file=None)

    assert settings.gemini_model == "gemini-test-model"
