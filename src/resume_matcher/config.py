from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Resume Matching API"
    app_version: str = "0.1.0"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    max_pdf_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    provider_timeout_seconds: float = 45.0
    overall_timeout_seconds: float = 110.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
