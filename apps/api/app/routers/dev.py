"""Development and demo endpoints for clock jumps and testing."""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.clock import Clock, get_clock
from app.config import settings
from app.db import get_db
from app.workflows.activities import emit_transition

router = APIRouter(prefix="/dev", tags=["dev"])


class TickRequest(BaseModel):
    minutes: int = 1
    seconds: Optional[int] = 0
    user_id: Optional[str] = None


@router.post("/tick")
async def dev_tick_post(
    req: Optional[TickRequest] = None,
    clock: Clock = Depends(get_clock),
):
    if settings.ENV == "production":
        raise HTTPException(status_code=403, detail="Forbidden in production")

    minutes = req.minutes if req else 1
    seconds = req.seconds if req and req.seconds is not None else 0
    delta = timedelta(minutes=minutes, seconds=seconds)

    if hasattr(clock, "advance"):
        clock.advance(delta)

    now = clock.now()
    db = get_db()

    target_user_id = req.user_id if req else None
    if target_user_id:
        users = [{"_id": target_user_id}]
    else:
        users = await db.users.find({}).to_list(length=100)

    transitions = 0
    boundary_id = f"tick-{now.isoformat()}"
    for user in users:
        uid = str(user["_id"])
        try:
            count = await emit_transition(uid, boundary_id)
            transitions += count
        except Exception:
            pass

    return {
        "status": "ok",
        "now": now.isoformat(),
        "advanced_minutes": minutes,
        "advanced_seconds": seconds,
        "transitions_emitted": transitions,
    }


@router.get("/tick")
async def dev_tick_get(
    minutes: int = 1,
    seconds: int = 0,
    user_id: Optional[str] = None,
    clock: Clock = Depends(get_clock),
):
    req = TickRequest(minutes=minutes, seconds=seconds, user_id=user_id)
    return await dev_tick_post(req, clock)
