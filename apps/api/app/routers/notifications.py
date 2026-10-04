"""In-app notification history and per-user SSE delivery."""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.clock import get_clock
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.core.security import get_current_user_id
from app.db import get_db
from app.domain.models import NotificationKind
from app.domain.notifications import (
    notification_broker,
    notification_policy,
)
from app.domain.visibility import can_view_for_connection, state_for_viewer

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationAction(BaseModel):
    action: Literal["CALL", "MESSAGE", "REMIND_LATER", "NONE"]


async def _can_read(db, notification: Dict[str, Any], viewer_id: str, now: datetime) -> bool:
    if notification.get("owner_only") and notification.get("about_owner") == viewer_id:
        return True
    try:
        kind = NotificationKind(notification["kind"])
    except (KeyError, ValueError):
        return False
    policy = notification_policy(kind)
    if policy.card is None:
        return False
    if not await can_view_for_connection(
        db,
        notification["about_owner"],
        viewer_id,
        policy.card,
        policy.required_level,
        now,
    ):
        return False
    state = await state_for_viewer(db, notification["about_owner"], viewer_id, now)
    return state is not None and not state.sharing_paused


@router.get("")
async def list_notifications(
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    notifications = await db.notifications.find({"to": current_user_id}).to_list(length=1000)
    visible = []
    for notification in notifications:
        if await _can_read(db, notification, current_user_id, clock.now()):
            visible.append(notification)
    return visible


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    notification = await db.notifications.find_one({
        "_id": notification_id,
        "to": current_user_id,
    })
    if not notification:
        raise NotFoundError("Notification not found")
    if not await _can_read(db, notification, current_user_id, clock.now()):
        raise ForbiddenError("Notification access is no longer active")
    await db.notifications.update_one(
        {"_id": notification_id, "to": current_user_id},
        {"$set": {"read_at": clock.now()}},
    )
    return {"id": notification_id, "read": True}


@router.post("/{notification_id}/action")
async def act_on_notification(
    notification_id: str,
    payload: NotificationAction,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    notification = await db.notifications.find_one({
        "_id": notification_id,
        "to": current_user_id,
    })
    if not notification:
        raise NotFoundError("Notification not found")
    if not await _can_read(db, notification, current_user_id, clock.now()):
        raise ForbiddenError("Notification access is no longer active")
    await db.notifications.update_one(
        {"_id": notification_id, "to": current_user_id},
        {"$set": {"action": payload.action, "read_at": clock.now()}},
    )
    return {"id": notification_id, "action": payload.action}


@router.get("/stream")
async def stream_notifications(
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    queue = notification_broker.subscribe(current_user_id)

    async def events():
        try:
            while True:
                try:
                    notification = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if await _can_read(db, notification, current_user_id, clock.now()):
                    yield f"data: {json.dumps(notification, default=str)}\n\n"
        finally:
            notification_broker.unsubscribe(current_user_id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )