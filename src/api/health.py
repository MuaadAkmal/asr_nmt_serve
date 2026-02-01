"""Health check and system info routes."""

from fastapi import APIRouter
import redis

from src.config import get_settings
from src.schemas.schemas import HealthResponse, LanguageInfo
from src.services.storage import storage_service

router = APIRouter(tags=["System"])

settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the service and its dependencies.",
)
async def health_check():
    """
    Health check endpoint.

    Returns the status of:
    - API server
    - Database connection
    - Redis connection
    - Object storage connection
    """
    # Check Redis
    redis_status = "ok"
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:
        redis_status = "error"

    # Check storage
    storage_status = "ok" if storage_service.health_check() else "error"

    # Check database (simplified - in production, do a real query)
    db_status = "ok"
    try:
        from src.db.session import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        db_status = "error"

    overall_status = "healthy"
    if any(s == "error" for s in [redis_status, storage_status, db_status]):
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        database=db_status,
        redis=redis_status,
        storage=storage_status,
    )


@router.get(
    "/v1/languages",
    response_model=list[LanguageInfo],
    summary="List supported languages",
    description="Get a list of all supported languages for ASR and NMT.",
)
async def list_languages():
    """Get list of supported languages."""
    languages = []

    for code, name in settings.language_names.items():
        languages.append(
            LanguageInfo(
                code=code,
                name=name,
                asr_supported=code in settings.primary_languages,
                nmt_supported=True,  # All languages support NMT
                auto_detect=True,  # All support auto-detection
            )
        )

    return languages


@router.get(
    "/v1/info",
    summary="Service information",
    description="Get general information about the service.",
)
async def service_info():
    """Get service information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
        "supported_job_types": ["asr", "nmt", "asr+nmt"],
        "supported_languages": list(settings.language_names.keys()),
        "primary_asr_model": "openai-whisper",
        "fallback_asr_model": "fb-omni",
        "documentation": "/docs",
        "redoc": "/redoc",
    }
