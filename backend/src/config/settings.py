from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: Literal["main", "demo", "test"] = "main"
    database_url: str = "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent"
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    upload_dir: Path = Path("backend/data/runtime/uploads")
    derived_dir: Path = Path("backend/data/runtime/derived")
    ocr_enabled: bool = False
    ocr_lang: str = "chi_sim+eng"
    ocr_max_pages: int = 5
    tesseract_cmd: str = ""
    ocrmypdf_cmd: str = "ocrmypdf"
    openai_compatible_api_base: str = "https://api.deepseek.com"
    openai_compatible_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"
    llm_thinking_type: Literal["enabled", "disabled"] = "enabled"
    llm_reasoning_effort: Literal["high", "max"] = "high"
    llm_response_format: Literal["json_object"] = "json_object"
    llm_max_tokens: int = Field(default=4096, ge=512, le=8192)
    llm_timeout_seconds: int = Field(default=120, ge=1, le=600)
    llm_max_retries: int = Field(default=2, ge=0, le=3)
    llm_retry_delay_seconds: float = Field(default=2, ge=0, le=60)
    llm_max_concurrency: int = Field(default=8, ge=1, le=16)
    llm_max_calls_per_run: int = Field(default=200, ge=1, le=1000)
    llm_prompt_version: str = "deepseek-gri-assist-v1"

    @field_validator("upload_dir", "derived_dir")
    @classmethod
    def resolve_project_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return PROJECT_ROOT / value

    @field_validator("openai_compatible_api_base")
    @classmethod
    def validate_llm_api_base(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("OPENAI_COMPATIBLE_API_BASE must be an HTTPS URL")
        return normalized

    @model_validator(mode="after")
    def validate_environment_targets(self) -> "Settings":
        if self.app_env == "demo":
            from src.config.environment_safety import validate_demo_environment

            validate_demo_environment(
                app_env=self.app_env,
                database_url=self.database_url,
                upload_dir=self.upload_dir,
                derived_dir=self.derived_dir,
            )
        return self

    def llm_configuration_summary(self) -> dict[str, object]:
        return {
            "api_base": self.openai_compatible_api_base,
            "api_key_present": bool(self.openai_compatible_api_key.strip()),
            "model": self.llm_model,
            "thinking_type": self.llm_thinking_type,
            "reasoning_effort": self.llm_reasoning_effort,
            "response_format": self.llm_response_format,
            "max_tokens": self.llm_max_tokens,
            "timeout_seconds": self.llm_timeout_seconds,
            "max_retries": self.llm_max_retries,
            "max_concurrency": self.llm_max_concurrency,
            "max_calls_per_run": self.llm_max_calls_per_run,
            "prompt_version": self.llm_prompt_version,
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
