from pathlib import Path

import yaml
from pydantic import ValidationError

from resume_matcher.domain.errors import RubricConfigurationError
from resume_matcher.domain.models import RubricConfig


def load_rubric(path: Path) -> RubricConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return RubricConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
        raise RubricConfigurationError(str(exc)) from exc
