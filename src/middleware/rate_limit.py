"""Rate limiting middleware using SlowAPI."""

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import get_settings

settings = get_settings()


def get_api_key_or_ip(request: Request) -> str:
    """
    Get rate limit key from API key or IP address.

    Uses API key if authenticated, falls back to IP address.
    """
    # Try to get API key from request state (set by auth middleware)
    if hasattr(request.state, "api_key") and request.state.api_key:
        return f"key:{request.state.api_key.id}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


# Create limiter with Redis storage
limiter = Limiter(
    key_func=get_api_key_or_ip,
    storage_uri=settings.redis_url,
    strategy="fixed-window",
)


def get_rate_limit_string(request: Request) -> str:
    """
    Get rate limit string based on API key's configured limits.

    Returns format like "60/minute;500/hour"
    """
    if hasattr(request.state, "api_key") and request.state.api_key:
        api_key = request.state.api_key
        return f"{api_key.rate_limit_per_minute}/minute;{api_key.rate_limit_per_hour}/hour"

    # Default limits for unauthenticated requests
    return f"{settings.rate_limit_per_minute}/minute;{settings.rate_limit_per_hour}/hour"


# Custom rate limit decorators
def rate_limit_jobs():
    """Rate limit for job creation endpoint."""
    return limiter.limit(
        f"{settings.rate_limit_per_minute}/minute",
        key_func=get_api_key_or_ip,
    )


def rate_limit_general():
    """Rate limit for general endpoints."""
    return limiter.limit(
        f"{settings.rate_limit_per_minute * 2}/minute",
        key_func=get_api_key_or_ip,
    )
