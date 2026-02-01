"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============== Language Enums ==============

SUPPORTED_LANGUAGES = {"en", "hi", "kn", "mr", "te", "ml", "ta"}
LANGUAGE_ALIASES = {
    "eng": "en",
    "english": "en",
    "hindi": "hi",
    "kannada": "kn",
    "marathi": "mr",
    "telugu": "te",
    "malayalam": "ml",
    "tamil": "ta",
}


def normalize_language(lang: str | None) -> str | None:
    """Normalize language code to standard format."""
    if lang is None:
        return None
    lang = lang.lower().strip()
    return LANGUAGE_ALIASES.get(lang, lang)


# ============== Job Schemas ==============


class TaskItemCreate(BaseModel):
    """Single item in a batch job request."""

    id: Optional[str] = Field(None, description="Client-provided unique ID for this item")
    audio_url: Optional[str] = Field(None, description="URL to audio file")
    audio_b64: Optional[str] = Field(None, description="Base64-encoded audio data")
    text: Optional[str] = Field(None, description="Text input (for NMT-only jobs)")
    src_lang: Optional[str] = Field(None, description="Source language code (overrides job default)")
    tgt_lang: Optional[str] = Field(None, description="Target language code (overrides job default)")

    @field_validator("src_lang", "tgt_lang", mode="before")
    @classmethod
    def normalize_lang(cls, v: str | None) -> str | None:
        return normalize_language(v)


class JobCreateRequest(BaseModel):
    """Request to create a new batch job."""

    job_type: Literal["asr", "nmt", "asr+nmt"] = Field(
        ..., description="Type of processing to perform"
    )
    items: list[TaskItemCreate] = Field(
        ..., min_length=1, max_length=1000, description="List of items to process"
    )
    default_src_lang: Optional[str] = Field(
        None, description="Default source language (auto-detect if not provided)"
    )
    default_tgt_lang: Optional[str] = Field(
        None, description="Default target language (required for nmt/asr+nmt)"
    )
    priority: int = Field(5, ge=1, le=10, description="Job priority (1-10, higher = more urgent)")
    callback_url: Optional[str] = Field(None, description="Webhook URL for job completion callback")
    metadata: Optional[dict] = Field(None, description="Custom metadata to attach to job")

    @field_validator("default_src_lang", "default_tgt_lang", mode="before")
    @classmethod
    def normalize_lang(cls, v: str | None) -> str | None:
        return normalize_language(v)


class JobCreateResponse(BaseModel):
    """Response after creating a job."""

    job_id: str
    job_type: str
    status: str
    enqueued_tasks: int
    created_at: datetime


class TaskStatusResponse(BaseModel):
    """Status of an individual task."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    external_id: Optional[str] = None
    status: str
    src_lang: Optional[str] = None
    tgt_lang: Optional[str] = None
    detected_lang: Optional[str] = None
    asr_result: Optional[str] = None
    nmt_result: Optional[str] = None
    asr_model_used: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobStatusResponse(BaseModel):
    """Full job status with all tasks."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    status: str
    priority: int
    default_src_lang: Optional[str] = None
    default_tgt_lang: Optional[str] = None
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress_percent: float
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: list[TaskStatusResponse] = []


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobStatusResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============== API Key Schemas ==============


class ApiKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100)
    owner: str = Field(..., min_length=1, max_length=100)
    scopes: list[Literal["asr", "nmt", "asr+nmt"]] = Field(
        default=["asr", "nmt", "asr+nmt"]
    )
    rate_limit_per_minute: int = Field(60, ge=1, le=10000)
    rate_limit_per_hour: int = Field(500, ge=1, le=100000)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    """Response after creating an API key (only time full key is shown)."""

    id: str
    api_key: str  # Full key, shown only once
    key_prefix: str
    name: str
    owner: str
    scopes: list[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    created_at: datetime
    expires_at: Optional[datetime] = None


class ApiKeyInfo(BaseModel):
    """API key info (without full key)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    key_prefix: str
    name: str
    owner: str
    scopes: list[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None


# ============== Health & Misc Schemas ==============


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    redis: str
    storage: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class LanguageInfo(BaseModel):
    """Information about a supported language."""

    code: str
    name: str
    asr_supported: bool
    nmt_supported: bool
    auto_detect: bool
