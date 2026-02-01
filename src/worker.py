"""Celery worker configuration and tasks."""

import time
from datetime import datetime, timezone

from celery import Celery, Task
from celery.signals import worker_ready

from src.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "asr_nmt_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # Soft limit at 9 minutes
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    task_acks_late=True,  # Ack after task completes
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "asr": {"exchange": "asr", "routing_key": "asr"},
        "nmt": {"exchange": "nmt", "routing_key": "nmt"},
        "high_priority": {"exchange": "high_priority", "routing_key": "high_priority"},
    },
    task_routes={
        "src.worker.process_asr_task": {"queue": "asr"},
        "src.worker.process_nmt_task": {"queue": "nmt"},
        "src.worker.process_task": {"queue": "default"},
    },
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "src.worker.cleanup_old_jobs",
            "schedule": 3600.0,  # Every hour
        },
    },
)


class BaseTask(Task):
    """Base task with retry configuration."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3


@celery_app.task(bind=True, base=BaseTask, name="src.worker.process_task")
def process_task(self, task_payload: dict) -> dict:
    """
    Process a single task (ASR, NMT, or ASR+NMT).

    Args:
        task_payload: Dict containing task details:
            - task_id: Task ID in database
            - job_id: Parent job ID
            - job_type: "asr", "nmt", or "asr+nmt"
            - input_type: "audio_url", "audio_b64", or "text"
            - input_ref: The actual input data
            - src_lang: Source language
            - tgt_lang: Target language

    Returns:
        Dict with results
    """
    from src.db.models import ASRModel, TaskStatus
    from src.db.session import async_session_maker
    from src.services.asr import asr_service
    from src.services.job_service import job_service
    from src.services.nmt import nmt_service
    from src.services.storage import storage_service
    from src.worker import trigger_webhook_if_needed
    import asyncio

    task_id = task_payload["task_id"]
    job_id = task_payload["job_id"]
    job_type = task_payload["job_type"]
    input_type = task_payload["input_type"]
    input_ref = task_payload["input_ref"]
    src_lang = task_payload.get("src_lang")
    tgt_lang = task_payload.get("tgt_lang")

    start_time = time.time()
    webhook_callback_url = None  # Will be set if job completes

    async def update_db(status, **kwargs):
        nonlocal webhook_callback_url
        async with async_session_maker() as db:
            await job_service.update_task_status(db, task_id, status, **kwargs)
            new_status, callback_url = await job_service.update_job_progress(db, job_id)
            await db.commit()
            # If job just completed and has callback, store it for webhook
            if callback_url:
                webhook_callback_url = callback_url

    try:
        # Update status to processing
        asyncio.get_event_loop().run_until_complete(
            update_db(TaskStatus.PROCESSING)
        )

        result = {
            "task_id": task_id,
            "asr_text": None,
            "nmt_text": None,
            "detected_lang": None,
            "model_used": None,
        }

        # Step 1: Get audio data if needed for ASR
        audio_data = None
        if job_type in ("asr", "asr+nmt"):
            if input_type == "audio_url":
                # Download from storage or URL
                import httpx
                response = httpx.get(input_ref, follow_redirects=True)
                response.raise_for_status()
                audio_data = response.content
            elif input_type == "audio_b64":
                import base64
                audio_data = base64.b64decode(input_ref)
            else:
                raise ValueError(f"Invalid input type for ASR: {input_type}")

        # Step 2: Run ASR if needed
        if job_type in ("asr", "asr+nmt"):
            if src_lang:
                asr_result = asr_service.transcribe(audio_data, src_lang)
            else:
                asr_result = asr_service.transcribe_with_detection(audio_data)

            result["asr_text"] = asr_result.text
            result["detected_lang"] = asr_result.detected_language
            result["model_used"] = asr_result.model_used

        # Step 3: Run NMT if needed
        text_to_translate = None
        if job_type == "nmt":
            text_to_translate = input_ref
        elif job_type == "asr+nmt":
            text_to_translate = result["asr_text"]

        if job_type in ("nmt", "asr+nmt") and text_to_translate:
            if not tgt_lang:
                raise ValueError("Target language required for NMT")

            effective_src = src_lang or result.get("detected_lang") or "en"
            nmt_result = nmt_service.translate(
                text_to_translate, effective_src, tgt_lang
            )
            result["nmt_text"] = nmt_result.translated_text

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update database with results
        asyncio.get_event_loop().run_until_complete(
            update_db(
                TaskStatus.COMPLETED,
                asr_result=result["asr_text"],
                nmt_result=result["nmt_text"],
                detected_lang=result["detected_lang"],
                asr_model_used=result["model_used"],
                processing_time_ms=processing_time_ms,
            )
        )

        # Trigger webhook if job just completed
        if webhook_callback_url:
            trigger_webhook_if_needed(job_id, webhook_callback_url)

        return result

    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update database with error
        asyncio.get_event_loop().run_until_complete(
            update_db(
                TaskStatus.FAILED,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
            )
        )

        # Trigger webhook if job just completed (even on failure)
        if webhook_callback_url:
            trigger_webhook_if_needed(job_id, webhook_callback_url)

        # Re-raise for Celery retry logic
        raise


@celery_app.task(name="src.worker.cleanup_old_jobs")
def cleanup_old_jobs():
    """Periodic task to clean up old completed jobs."""
    import asyncio
    from datetime import timedelta
    from sqlalchemy import delete, select
    from src.db.session import async_session_maker
    from src.db.models import Job, JobStatus
    from src.services.storage import storage_service
    import logging

    logger = logging.getLogger(__name__)

    async def do_cleanup():
        async with async_session_maker() as db:
            # Delete jobs older than 7 days that are completed/failed
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Get old jobs to clean up storage
            result = await db.execute(
                select(Job).where(
                    Job.completed_at < cutoff,
                    Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PARTIAL])
                )
            )
            old_jobs = list(result.scalars().all())
            
            for job in old_jobs:
                try:
                    # Delete files from storage
                    storage_service.delete_job_files(job.id)
                    logger.info(f"Deleted storage files for job {job.id}")
                except Exception as e:
                    logger.error(f"Failed to delete storage for job {job.id}: {e}")
                
                # Delete job from database (cascades to tasks)
                await db.delete(job)
            
            await db.commit()
            logger.info(f"Cleaned up {len(old_jobs)} old jobs")

    asyncio.get_event_loop().run_until_complete(do_cleanup())


@celery_app.task(name="src.worker.send_webhook", bind=True, max_retries=3)
def send_webhook(self, job_id: str, callback_url: str):
    """
    Send webhook notification when job completes.
    
    Retries up to 3 times with exponential backoff.
    """
    import httpx
    import asyncio
    import logging
    from src.db.session import async_session_maker
    from src.db.models import Job
    from sqlalchemy import select

    logger = logging.getLogger(__name__)

    async def get_job_data():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Job).where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                return None
            
            return {
                "job_id": job.id,
                "job_type": job.job_type.value,
                "status": job.status.value,
                "total_tasks": job.total_tasks,
                "completed_tasks": job.completed_tasks,
                "failed_tasks": job.failed_tasks,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }

    try:
        # Get job data from database
        job_data = asyncio.get_event_loop().run_until_complete(get_job_data())
        
        if not job_data:
            logger.error(f"Job {job_id} not found for webhook")
            return

        payload = {
            "event": "job.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": job_data,
        }

        # Send webhook with timeout
        response = httpx.post(
            callback_url,
            json=payload,
            timeout=30,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ASR-NMT-Service/1.0",
                "X-Webhook-Event": "job.completed",
            },
        )
        response.raise_for_status()
        logger.info(f"Webhook sent successfully for job {job_id} to {callback_url}")

    except httpx.HTTPStatusError as e:
        logger.error(f"Webhook HTTP error for job {job_id}: {e.response.status_code}")
        # Retry on 5xx errors
        if e.response.status_code >= 500:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except httpx.RequestError as e:
        logger.error(f"Webhook request error for job {job_id}: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except Exception as e:
        logger.error(f"Webhook failed for job {job_id}: {e}")


def trigger_webhook_if_needed(job_id: str, callback_url: str | None):
    """
    Trigger webhook task if callback URL is set.
    
    Call this after job status changes to completed/failed/partial.
    """
    if callback_url:
        send_webhook.apply_async(
            args=[job_id, callback_url],
            countdown=5,  # Small delay to ensure DB is committed
        )


def enqueue_job_tasks(job_id: str, tasks: list[dict], priority: int = 5):
    """
    Enqueue all tasks for a job.

    Args:
        job_id: Job ID
        tasks: List of task payloads
        priority: Job priority (1-10)
    """
    # Map priority to Celery priority (0-9, lower = higher priority)
    celery_priority = 10 - priority

    for task_payload in tasks:
        task_payload["job_id"] = job_id

        # Determine queue based on job type
        job_type = task_payload.get("job_type", "asr")
        if job_type == "nmt":
            queue = "nmt"
        elif job_type in ("asr", "asr+nmt"):
            queue = "asr"
        else:
            queue = "default"

        # Use high priority queue for urgent jobs
        if priority >= 8:
            queue = "high_priority"

        process_task.apply_async(
            args=[task_payload],
            queue=queue,
            priority=celery_priority,
        )
