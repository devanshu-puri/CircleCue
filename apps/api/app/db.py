import logging
from typing import Optional
from pymongo import AsyncMongoClient, IndexModel, ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.config import settings

logger = logging.getLogger("circlecue.db")

_client: Optional[AsyncMongoClient] = None
_db: Optional[AsyncDatabase] = None

def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(settings.MONGODB_URI)
    return _client

def get_db() -> AsyncDatabase:
    global _db
    if _db is None:
        client = get_client()
        # Parse database name from URI or default to "circlecue"
        db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "circlecue"
        _db = client[db_name]
    return _db

async def ensure_indexes() -> None:
    """Ensure database indexes are created idempotently at application startup."""
    db = get_db()
    
    # 1. users: user_code unique
    await db.users.create_index([("user_code", ASCENDING)], unique=True)
    
    # 2. grants: (owner, viewer) unique
    await db.grants.create_index([("owner", ASCENDING), ("viewer", ASCENDING)], unique=True)
    
    # 3. notifications: (to, created_at), dedupe_key (unique, sparse)
    await db.notifications.create_index([("to", ASCENDING), ("created_at", DESCENDING)])
    await db.notifications.create_index([("dedupe_key", ASCENDING)], unique=True, sparse=True)
    
    # 4. activities: (owner, status, expected_end_at)
    await db.activities.create_index([
        ("owner", ASCENDING),
        ("status", ASCENDING),
        ("expected_end_at", ASCENDING)
    ])
    
    # 5. templates: (owner)
    await db.templates.create_index([("owner", ASCENDING)])
    
    # 6. call_events: (caller, callee, ts)
    await db.call_events.create_index([
        ("caller", ASCENDING),
        ("callee", ASCENDING),
        ("ts", DESCENDING)
    ])

    logger.info("MongoDB indexes verified successfully.")
