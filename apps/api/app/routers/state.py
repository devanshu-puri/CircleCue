"""State API router: GET /state/me, GET /state/{owner_id}, GET /timeline?date="""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from zoneinfo import ZoneInfo

from app.db import get_db
from app.core.security import get_current_user_id
from app.core.errors import NotFoundError, ForbiddenError
from app.clock import get_clock
from app.domain.resolver import resolve, UserBundle
from app.domain.expander import expand
from app.domain.freewindows import free_windows
from app.domain.visibility import state_for_viewer, timeline_for_viewer

router = APIRouter(tags=["state"])


async def _build_bundle(db, user_id: str) -> Optional[UserBundle]:
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return None

    acts_cursor = db.activities.find({"owner": user_id, "status": {"$nin": ["COMPLETED", "CANCELLED"]}})
    activities = await acts_cursor.to_list(length=500)

    tmpls_cursor = db.templates.find({"owner": user_id})
    templates = await tmpls_cursor.to_list(length=500)

    excs_cursor = db.exceptions.find({"owner": user_id})
    exceptions = await excs_cursor.to_list(length=500)

    exams_cursor = db.exam_sets.find({"owner": user_id})
    exam_sets = await exams_cursor.to_list(length=500)

    phone = await db.phone_state.find_one({"_id": user_id})

    scenarios_cursor = db.scenarios.find({"owner": user_id, "enabled": True})
    scenarios = await scenarios_cursor.to_list(length=200)

    return UserBundle(
        owner_id=user_id,
        tz=user.get("tz", "UTC"),
        routine_prefs=user.get("routine_prefs", {}),
        sharing_paused=user.get("sharing_paused", {}),
        activities=activities,
        templates=templates,
        exceptions=exceptions,
        exam_sets=exam_sets,
        phone_state=phone,
        current_place=user.get("current_place"),
        scenarios=scenarios,
    )


@router.get("/state/me")
async def get_my_state(
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    bundle = await _build_bundle(db, current_user_id)
    if not bundle:
        raise NotFoundError("User not found")
    now = clock.now()
    state = resolve(bundle, now)
    return state.model_dump()


@router.get("/state/{owner_id}")
async def get_owner_state(
    owner_id: str,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    """All reads of another user's data go through visibility.project."""
    db = get_db()
    now = clock.now()

    viewer_state = await state_for_viewer(db, owner_id, current_user_id, now)
    if not viewer_state:
        raise ForbiddenError("No active connection with this user")
    return viewer_state.model_dump()


@router.get("/timeline")
async def get_my_timeline(
    date_str: Optional[str] = Query(default=None, alias="date"),
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    now = clock.now()

    user = await db.users.find_one({"_id": current_user_id})
    if not user:
        raise NotFoundError("User not found")

    tz = user.get("tz", "UTC")
    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = now.astimezone(ZoneInfo(tz)).date()

    tmpls_cursor = db.templates.find({"owner": current_user_id})
    templates = await tmpls_cursor.to_list(length=500)
    excs_cursor = db.exceptions.find({"owner": current_user_id})
    exceptions = await excs_cursor.to_list(length=500)
    exams_cursor = db.exam_sets.find({"owner": current_user_id})
    exam_sets = await exams_cursor.to_list(length=500)

    segments = expand(templates, exceptions, exam_sets, target_date, tz)
    routine = user.get("routine_prefs", {})
    min_window = routine.get("min_call_window_min", 10)
    buffer = routine.get("buffer_min", 5)

    day_start_str = routine.get("wake", "07:00")
    day_end_str = routine.get("sleep", "23:00")
    zi = ZoneInfo(tz)
    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         int(day_start_str[:2]), int(day_start_str[3:5]), tzinfo=zi).astimezone(timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day,
                       int(day_end_str[:2]), int(day_end_str[3:5]), tzinfo=zi).astimezone(timezone.utc)

    windows = free_windows(segments, day_start, day_end, min_window, buffer)

    return {
        "date": target_date.isoformat(),
        "tz": tz,
        "segments": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "activity_type": s.activity_type,
                "label": s.label,
                "calls_ok": s.calls_ok,
            }
            for s in segments
        ],
        "free_windows": [
            {
                "start": w.start.isoformat(),
                "end": w.end.isoformat(),
                "net_minutes": w.net_minutes,
            }
            for w in windows
        ],
    }


@router.get("/timeline/{owner_id}")
async def get_owner_timeline(
    owner_id: str,
    date_str: Optional[str] = Query(default=None, alias="date"),
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    target_date = date.fromisoformat(date_str) if date_str else None
    timeline = await timeline_for_viewer(
        db, owner_id, current_user_id, clock.now(), target_date
    )
    if timeline is None:
        raise ForbiddenError("Schedule is not shared with this user")
    return timeline
