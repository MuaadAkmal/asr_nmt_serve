"""Script to create an initial admin API key."""

import asyncio
import sys

sys.path.insert(0, ".")

from src.auth.security import create_api_key
from src.db.session import async_session_maker, init_db


async def main():
    """Create initial admin API key."""
    print("Initializing database...")
    await init_db()

    print("Creating admin API key...")
    async with async_session_maker() as db:
        api_key, full_key = await create_api_key(
            db,
            name="Admin Key",
            owner="admin",
            scopes=["asr", "nmt", "asr+nmt"],
            rate_limit_per_minute=1000,
            rate_limit_per_hour=10000,
            expires_in_days=None,  # Never expires
        )
        await db.commit()

        print("\n" + "=" * 60)
        print("ADMIN API KEY CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"\nAPI Key: {full_key}")
        print(f"Key ID:  {api_key.id}")
        print(f"Prefix:  {api_key.key_prefix}")
        print("\n⚠️  SAVE THIS KEY NOW - IT WILL NOT BE SHOWN AGAIN!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
