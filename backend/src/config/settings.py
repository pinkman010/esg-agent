from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent"
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    upload_dir: Path = Path("backend/data/runtime/uploads")
    derived_dir: Path = Path("backend/data/runtime/derived")
    ocr_enabled: bool = False
    ocr_lang: str = "chi_sim+eng"
    ocr_max_pages: int = 5
    tesseract_cmd: str = ""
    ocrmypdf_cmd: str = "ocrmypdf"
    openai_compatible_api_base: str = ""
    openai_compatible_api_key: str = ""
    llm_model: str = "deepseek-v4-flash"

    @field_validator("upload_dir", "derived_dir")
    @classmethod
    def resolve_project_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return PROJECT_ROOT / value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
