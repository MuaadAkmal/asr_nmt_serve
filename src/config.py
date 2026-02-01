"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "asr-nmt-service"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/asr_nmt_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3 Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "asr-nmt-uploads"
    minio_use_ssl: bool = False

    # Whisper Model Configuration
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_concurrency: int = 2

    # Omni ASR (FB Seamless)
    omni_concurrency: int = 1

    # NMT Configuration
    nmt_concurrency: int = 2

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 500

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Logging
    log_level: str = "INFO"

    # Supported Languages
    @property
    def primary_languages(self) -> set[str]:
        """Languages supported by OpenAI Whisper (primary ASR)."""
        return {"en", "hi", "kn", "mr", "te", "ml", "ta"}

    @property
    def language_names(self) -> dict[str, str]:
        """Human-readable language names."""
        return {
            "en": "English",
            "hi": "Hindi",
            "kn": "Kannada",
            "mr": "Marathi",
            "te": "Telugu",
            "ml": "Malayalam",
            "ta": "Tamil",
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
