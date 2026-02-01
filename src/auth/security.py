"""Authentication and authorization utilities."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ApiKey
from src.db.session import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> tuple[str, str]:
    """  
    Generate a new API key.
    Returns: (full_key, prefix)
    Format: ask_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (32 random chars after prefix)
    """
    random_part = secrets.token_hex(16)  # 32 hex chars
    full_key = f"ask_{random_part}"
    prefix = full_key[:12]  # "ask_" + first 8 chars
    return full_key, prefix


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return pwd_context.hash(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return pwd_context.verify(plain_key, hashed_key)


async def get_api_key_from_db(
    db: AsyncSession, key_prefix: str, full_key: str
) -> Optional[ApiKey]:
    """Look up an API key by prefix and verify the full key."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active == True,  
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

     if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

     if not verify_api_key(full_key, api_key.key_hash):
        return None

    return api_key


class AuthenticatedApiKey:
    """Dependency for authenticated API key."""

    def __init__(self, required_scopes: Optional[list[str]] = None):
        self.required_scopes = required_scopes or []

    async def __call__(
        self,
        request: Request,
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
    ) -> ApiKey:
        """Extract and validate API key from request."""
        # Try Authorization header first, then X-API-Key
        api_key_str = None

        if authorization:
            if authorization.startswith("Bearer "):
                api_key_str = authorization[7:]
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization scheme. Use 'Bearer <api_key>'",
                )
        elif x_api_key:
            api_key_str = x_api_key

        if not api_key_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key. Provide via 'Authorization: Bearer <key>' or 'X-API-Key' header",
            )

        # Validate format
        if not api_key_str.startswith("ask_") or len(api_key_str) != 36:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format",
            )

        # Look up and verify
        prefix = api_key_str[:12]
        api_key = await get_api_key_from_db(db, prefix, api_key_str)

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired API key",
            )

        # Check scopes
        if self.required_scopes:
            key_scopes = set(api_key.scopes or [])
            required = set(self.required_scopes)
            if not required.intersection(key_scopes):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API key lacks required scope(s): {self.required_scopes}",
                )

        # Store in request state for later use
        request.state.api_key = api_key
        return api_key


# Convenience dependency instances
require_auth = AuthenticatedApiKey()
require_asr_scope = AuthenticatedApiKey(required_scopes=["asr", "asr+nmt"])
require_nmt_scope = AuthenticatedApiKey(required_scopes=["nmt", "asr+nmt"])
require_any_scope = AuthenticatedApiKey(required_scopes=["asr", "nmt", "asr+nmt"])


async def create_api_key(
    db: AsyncSession,
    name: str,
    owner: str,
    scopes: list[str],
    rate_limit_per_minute: int = 60,
    rate_limit_per_hour: int = 500,
    expires_in_days: Optional[int] = None,
) -> tuple[ApiKey, str]:
    """
    Create a new API key.
    Returns: (ApiKey model, full_key_string)
    """
    full_key, prefix = generate_api_key()
    hashed = hash_api_key(full_key)

    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    api_key = ApiKey(
        key_hash=hashed,
        key_prefix=prefix,
        name=name,
        owner=owner,
        scopes=scopes,
        rate_limit_per_minute=rate_limit_per_minute,
        rate_limit_per_hour=rate_limit_per_hour,
        expires_at=expires_at,
    )

    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return api_key, full_key
