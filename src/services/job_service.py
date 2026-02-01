"""Job management service."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import ApiKey, Job, JobStatus, JobType, Task, TaskStatus
from src.schemas.schemas import JobCreateRequest, JobStatusResponse, TaskStatusResponse


class JobService:
    """Service for managing jobs and tasks."""

    async def create_job(
        self,
        db: AsyncSession,
        request: JobCreateRequest,
        api_key: ApiKey,
    ) -> Job:
        """
        Create a new job with tasks.

        Args:
            db: Database session
            request: Job creation request
            api_key: Authenticated API key

        Returns:
            Created Job with tasks
        """
        # Create job
        job = Job(
            id=str(uuid4()),
            api_key_id=api_key.id,
            job_type=JobType(request.job_type),
            status=JobStatus.PENDING,
            default_src_lang=request.default_src_lang,
            default_tgt_lang=request.default_tgt_lang,
            priority=request.priority,
            total_tasks=len(request.items),
            callback_url=request.callback_url,
            metadata=request.metadata,
        )
        db.add(job)

        # Create tasks for each item
        tasks = []
        for item in request.items:
            # Determine input type
            if item.audio_url:
                input_type = "audio_url"
                input_ref = item.audio_url
            elif item.audio_b64:
                input_type = "audio_b64"
                input_ref = item.audio_b64
            elif item.text:
                input_type = "text"
                input_ref = item.text
            else:
                raise ValueError(f"Item {item.id} has no valid input")

            task = Task(
                id=str(uuid4()),
                job_id=job.id,
                external_id=item.id,
                input_type=input_type,
                input_ref=input_ref,
                src_lang=item.src_lang or request.default_src_lang,
                tgt_lang=item.tgt_lang or request.default_tgt_lang,
                status=TaskStatus.PENDING,
            )
            tasks.append(task)
            db.add(task)

        await db.flush()
        await db.refresh(job)

        return job

    async def get_job(
        self,
        db: AsyncSession,
        job_id: str,
        api_key_id: Optional[str] = None,
        include_tasks: bool = True,
    ) -> Optional[Job]:
        """
        Get a job by ID.

        Args:
            db: Database session
            job_id: Job ID
            api_key_id: Filter by API key (for authorization)
            include_tasks: Whether to eagerly load tasks

        Returns:
            Job or None
        """
        query = select(Job).where(Job.id == job_id)

        if api_key_id:
            query = query.where(Job.api_key_id == api_key_id)

        if include_tasks:
            query = query.options(selectinload(Job.tasks))

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        db: AsyncSession,
        api_key_id: str,
        status: Optional[JobStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """
        List jobs for an API key.

        Returns:
            Tuple of (jobs, total_count)
        """
        # Base query
        query = select(Job).where(Job.api_key_id == api_key_id)

        if status:
            query = query.where(Job.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # Apply pagination
        query = (
            query.order_by(Job.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(query)
        jobs = list(result.scalars().all())

        return jobs, total

    async def get_tasks_for_job(
        self,
        db: AsyncSession,
        job_id: str,
    ) -> list[Task]:
        """Get all tasks for a job."""
        result = await db.execute(
            select(Task)
            .where(Task.job_id == job_id)
            .order_by(Task.created_at)
        )
        return list(result.scalars().all())

    async def update_job_status(
        self,
        db: AsyncSession,
        job_id: str,
        status: JobStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        """Update job status."""
        update_data = {"status": status}

        if started_at:
            update_data["started_at"] = started_at
        if completed_at:
            update_data["completed_at"] = completed_at

        await db.execute(
            update(Job).where(Job.id == job_id).values(**update_data)
        )

    async def update_task_status(
        self,
        db: AsyncSession,
        task_id: str,
        status: TaskStatus,
        asr_result: Optional[str] = None,
        nmt_result: Optional[str] = None,
        detected_lang: Optional[str] = None,
        asr_model_used: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
    ):
        """Update task status and results."""
        update_data = {"status": status}

        if asr_result is not None:
            update_data["asr_result"] = asr_result
        if nmt_result is not None:
            update_data["nmt_result"] = nmt_result
        if detected_lang is not None:
            update_data["detected_lang"] = detected_lang
        if asr_model_used is not None:
            update_data["asr_model_used"] = asr_model_used
        if error_message is not None:
            update_data["error_message"] = error_message
        if processing_time_ms is not None:
            update_data["processing_time_ms"] = processing_time_ms

        if status == TaskStatus.PROCESSING:
            update_data["started_at"] = datetime.now(timezone.utc)
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            update_data["completed_at"] = datetime.now(timezone.utc)

        await db.execute(
            update(Task).where(Task.id == task_id).values(**update_data)
        )

    async def update_job_progress(self, db: AsyncSession, job_id: str) -> tuple[str, str | None]:
        """
        Update job progress based on task statuses.
        Call this after updating task status.
        
        Returns:
            Tuple of (new_status, callback_url) - callback_url is set if job just completed
        """
        # Get task counts
        result = await db.execute(
            select(
                func.count().filter(Task.status == TaskStatus.COMPLETED).label("completed"),
                func.count().filter(Task.status == TaskStatus.FAILED).label("failed"),
                func.count().label("total"),
            ).where(Task.job_id == job_id)
        )
        row = result.one()
        completed = row.completed
        failed = row.failed
        total = row.total

        # Get current job to check previous status and callback_url
        job_result = await db.execute(select(Job).where(Job.id == job_id))
        job = job_result.scalar_one_or_none()
        previous_status = job.status if job else None
        callback_url = job.callback_url if job else None

        # Determine job status
        if completed + failed == total:
            if failed == 0:
                status = JobStatus.COMPLETED
            elif completed == 0:
                status = JobStatus.FAILED
            else:
                status = JobStatus.PARTIAL
            completed_at = datetime.now(timezone.utc)
        else:
            status = JobStatus.PROCESSING
            completed_at = None

        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                completed_tasks=completed,
                failed_tasks=failed,
                status=status,
                completed_at=completed_at,
            )
        )

        # Return callback_url only if job just transitioned to a final state
        should_webhook = (
            previous_status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PARTIAL)
            and status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PARTIAL)
        )
        
        return status.value, callback_url if should_webhook else None

    def job_to_response(self, job: Job) -> JobStatusResponse:
        """Convert Job model to response schema."""
        progress = 0.0
        if job.total_tasks > 0:
            progress = (job.completed_tasks + job.failed_tasks) / job.total_tasks * 100

        tasks = []
        if job.tasks:
            tasks = [
                TaskStatusResponse(
                    id=t.id,
                    external_id=t.external_id,
                    status=t.status.value,
                    src_lang=t.src_lang,
                    tgt_lang=t.tgt_lang,
                    detected_lang=t.detected_lang,
                    asr_result=t.asr_result,
                    nmt_result=t.nmt_result,
                    asr_model_used=t.asr_model_used.value if t.asr_model_used else None,
                    error_message=t.error_message,
                    processing_time_ms=t.processing_time_ms,
                    created_at=t.created_at,
                    completed_at=t.completed_at,
                )
                for t in job.tasks
            ]

        return JobStatusResponse(
            id=job.id,
            job_type=job.job_type.value,
            status=job.status.value,
            priority=job.priority,
            default_src_lang=job.default_src_lang,
            default_tgt_lang=job.default_tgt_lang,
            total_tasks=job.total_tasks,
            completed_tasks=job.completed_tasks,
            failed_tasks=job.failed_tasks,
            progress_percent=round(progress, 2),
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            tasks=tasks,
        )


# Singleton instance
job_service = JobService()
