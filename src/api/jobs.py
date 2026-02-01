"""Job management API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.security import require_any_scope
from src.db.models import ApiKey, JobStatus
from src.db.session import get_db
from src.schemas.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobListResponse,
    JobStatusResponse,
)
from src.services.job_service import job_service
from src.worker import enqueue_job_tasks

router = APIRouter(prefix="/v1/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new batch job",
    description="Create a new ASR, NMT, or ASR+NMT batch job with multiple items.",
)
async def create_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_any_scope),
):
    """
    Create a new batch job.

    - **job_type**: Type of processing ("asr", "nmt", or "asr+nmt")
    - **items**: List of items to process (audio URLs, base64, or text)
    - **default_src_lang**: Default source language (auto-detect if not provided)
    - **default_tgt_lang**: Default target language (required for nmt/asr+nmt)
    - **priority**: Job priority 1-10 (higher = more urgent)
    """
    # Validate job type and language requirements
    if request.job_type in ("nmt", "asr+nmt"):
        if not request.default_tgt_lang:
            # Check if all items have tgt_lang
            missing_tgt = [
                item for item in request.items
                if not item.tgt_lang
            ]
            if missing_tgt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target language required for NMT jobs",
                )

    # Validate input types for job type
    for i, item in enumerate(request.items):
        if request.job_type in ("asr", "asr+nmt"):
            if not item.audio_url and not item.audio_b64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item {i}: Audio required for ASR jobs",
                )
        elif request.job_type == "nmt":
            if not item.text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item {i}: Text required for NMT jobs",
                )

    # Create job in database
    job = await job_service.create_job(db, request, api_key)
    await db.commit()

    # Get tasks and enqueue them
    tasks = await job_service.get_tasks_for_job(db, job.id)
    task_payloads = [
        {
            "task_id": t.id,
            "job_type": request.job_type,
            "input_type": t.input_type,
            "input_ref": t.input_ref,
            "src_lang": t.src_lang,
            "tgt_lang": t.tgt_lang,
        }
        for t in tasks
    ]
    enqueue_job_tasks(job.id, task_payloads, request.priority)

    return JobCreateResponse(
        job_id=job.id,
        job_type=job.job_type.value,
        status=job.status.value,
        enqueued_tasks=len(tasks),
        created_at=job.created_at,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="Get a paginated list of jobs for the authenticated API key.",
)
async def list_jobs(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (pending, processing, completed, failed, partial)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_any_scope),
):
    """List all jobs for the authenticated API key."""
    status_enum = None
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    jobs, total = await job_service.list_jobs(
        db, api_key.id, status_enum, page, page_size
    )

    total_pages = (total + page_size - 1) // page_size

    return JobListResponse(
        jobs=[job_service.job_to_response(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Get detailed status and results of a specific job.",
)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_any_scope),
):
    """Get job details including all task statuses and results."""
    job = await job_service.get_job(db, job_id, api_key.id, include_tasks=True)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return job_service.job_to_response(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel/delete a job",
    description="Cancel a pending job or delete a completed job.",
)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_any_scope),
):
    """Cancel or delete a job."""
    job = await job_service.get_job(db, job_id, api_key.id, include_tasks=False)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # TODO: Cancel pending Celery tasks
    # TODO: Delete files from storage

    await db.delete(job)
    await db.commit()


@router.get(
    "/{job_id}/results",
    summary="Get job results",
    description="Get results for all completed tasks in a job.",
)
async def get_job_results(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_any_scope),
):
    """Get consolidated results for a job."""
    job = await job_service.get_job(db, job_id, api_key.id, include_tasks=True)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    results = []
    for task in job.tasks:
        result = {
            "task_id": task.id,
            "external_id": task.external_id,
            "status": task.status.value,
        }

        if task.status.value == "completed":
            if task.asr_result:
                result["transcription"] = task.asr_result
            if task.nmt_result:
                result["translation"] = task.nmt_result
            if task.detected_lang:
                result["detected_language"] = task.detected_lang
        elif task.status.value == "failed":
            result["error"] = task.error_message

        results.append(result)

    return {
        "job_id": job.id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "total_tasks": job.total_tasks,
        "completed_tasks": job.completed_tasks,
        "failed_tasks": job.failed_tasks,
        "results": results,
    }
