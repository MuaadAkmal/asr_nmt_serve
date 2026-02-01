"""Database models for ASR-NMT service."""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class JobType(str, enum.Enum):
    """Types of jobs supported by the service."""

    ASR = "asr"
    NMT = "nmt"
    ASR_NMT = "asr+nmt"


class JobStatus(str, enum.Enum):
    """Status of a job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some tasks completed, some failed


class TaskStatus(str, enum.Enum):
    """Status of an individual task within a job."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ASRModel(str, enum.Enum):
    """ASR models available."""

    WHISPER = "whisper"
    OMNI = "omni"  # FB Seamless / Omni


class ApiKey(Base):
    """API keys for authentication."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(10), index=True)  # First 8 chars for lookup
    name: Mapped[str] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100))
    scopes: Mapped[list] = mapped_column(JSON, default=list)  # ["asr", "nmt", "asr+nmt"]
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=500)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="api_key")


class Job(Base):
    """A batch job containing multiple tasks."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    api_key_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("api_keys.id"), index=True
    )
    job_type: Mapped[JobType] = mapped_column(Enum(JobType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)

    # Language settings
    default_src_lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    default_tgt_lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Metadata
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1-10, higher = more urgent
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    failed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Webhook URL
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    api_key: Mapped["ApiKey"] = relationship("ApiKey", back_populates="jobs")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="job", cascade="all, delete-orphan")


class Task(Base):
    """An individual task within a job (one audio file or text item)."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Client-provided ID

    # Input
    input_type: Mapped[str] = mapped_column(String(20))  # "audio_url", "audio_b64", "text"
    input_ref: Mapped[str] = mapped_column(Text)  # URL, base64, or text content
    input_storage_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Path in object storage

    # Language settings (override job defaults)
    src_lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tgt_lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    detected_lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Processing
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    asr_model_used: Mapped[Optional[ASRModel]] = mapped_column(Enum(ASRModel), nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Results
    asr_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Transcribed text
    nmt_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Translated text
    result_storage_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Path to result JSON in storage
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metrics
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="tasks")


class AuditLog(Base):
    """Audit log for tracking API usage and changes."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    api_key_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), index=True)  # e.g., "job.create", "task.complete"
    resource_type: Mapped[str] = mapped_column(String(50))  # "job", "task", "api_key"
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
