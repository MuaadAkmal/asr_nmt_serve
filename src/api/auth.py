"""API Key management routes (admin)."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.security import create_api_key
from src.config import get_settings
from src.db.models import ApiKey
from src.db.session import get_db
from src.schemas.schemas import ApiKeyCreate, ApiKeyInfo, ApiKeyResponse

router = APIRouter(prefix="/v1/admin/api-keys", tags=["Admin - API Keys"])

settings = get_settings()


def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """Verify admin access using a secret key."""
    if not x_admin_key or x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )
    return True


@router.post(
    "",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
    description="Create a new API key for accessing the service. Admin only.",
)
async def create_new_api_key(
    request: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_key),
):
    """
    Create a new API key.

    **Important**: The full API key is only shown once in this response.
    Store it securely as it cannot be retrieved later.
    """
    api_key_model, full_key = await create_api_key(
        db,
        name=request.name,
        owner=request.owner,
        scopes=request.scopes,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_hour=request.rate_limit_per_hour,
        expires_in_days=request.expires_in_days,
    )
    await db.commit()

    return ApiKeyResponse(
        id=api_key_model.id,
        api_key=full_key,  # Only time this is shown
        key_prefix=api_key_model.key_prefix,
        name=api_key_model.name,
        owner=api_key_model.owner,
        scopes=api_key_model.scopes,
        rate_limit_per_minute=api_key_model.rate_limit_per_minute,
        rate_limit_per_hour=api_key_model.rate_limit_per_hour,
        created_at=api_key_model.created_at,
        expires_at=api_key_model.expires_at,
    )


@router.get(
    "",
    response_model=list[ApiKeyInfo],
    summary="List all API keys",
    description="List all API keys (without the actual key values). Admin only.",
)
async def list_api_keys(
    include_inactive: bool = Query(False, description="Include inactive keys"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_key),
):
    """List all API keys."""
    query = select(ApiKey)
    if not include_inactive:
        query = query.where(ApiKey.is_active == True)  # noqa: E712

    query = query.order_by(ApiKey.created_at.desc())
    result = await db.execute(query)
    keys = list(result.scalars().all())

    return [
        ApiKeyInfo(
            id=k.id,
            key_prefix=k.key_prefix,
            name=k.name,
            owner=k.owner,
            scopes=k.scopes,
            rate_limit_per_minute=k.rate_limit_per_minute,
            rate_limit_per_hour=k.rate_limit_per_hour,
            is_active=k.is_active,
            created_at=k.created_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


@router.get(
    "/{key_id}",
    response_model=ApiKeyInfo,
    summary="Get API key details",
    description="Get details of a specific API key. Admin only.",
)
async def get_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_key),
):
    """Get API key details."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )

    return ApiKeyInfo(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        owner=api_key.owner,
        scopes=api_key.scopes,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        rate_limit_per_hour=api_key.rate_limit_per_hour,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
    description="Deactivate an API key (soft delete). Admin only.",
)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_key),
):
    """Revoke/deactivate an API key."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )

    api_key.is_active = False
    await db.commit()
