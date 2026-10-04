import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.db import get_db

logger = logging.getLogger("circlecue.audit")

async def log_audit_event(
    actor: str,
    action: str,
    target: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> None:
    try:
        db = get_db()
        doc = {
            "actor": actor,
            "action": action,
            "target": target,
            "meta": meta or {},
            "at": datetime.now(timezone.utc)
        }
        await db.audit_log.insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to write audit log event: {e}")
