"""Temporal activities: all database and notification I/O stays outside workflows."""
from datetime import datetime, timezone
from typing import Any
import sentry_sdk
from temporalio import activity

from app.clock import get_clock
from app.db import get_db
from app.domain.events import DomainEvent
from app.domain.models import ActivityType, NotificationKind
from app.domain.notifications import notification_broker, process_event
from app.domain.visibility import resolved_state_for_owner


def _tag_activity_scope() -> None:
    try:
        info = activity.info()
        sentry_sdk.set_tag("workflow_id", info.workflow_id)
        sentry_sdk.set_tag("workflow_type", info.workflow_type)
        sentry_sdk.set_tag("activity_type", info.activity_type)
    except Exception:
        pass


@activity.defn
async def compute_next_boundary(user_id: str) -> str | None:
    _tag_activity_scope()
    now = get_clock().now()
    state = await resolved_state_for_owner(get_db(), user_id, now)
    return state.next_boundary_at.isoformat() if state and state.next_boundary_at else None


@activity.defn
async def emit_transition(user_id: str, boundary_id: str) -> int:
    _tag_activity_scope()
    db = get_db()
    now = get_clock().now()
    state = await resolved_state_for_owner(db, user_id, now)
    delivered_count = 0

    if state and state.activity is not None:
        if state.activity.type == ActivityType.FREE:
            delivered_count += len(await process_event(
                db,
                DomainEvent(kind=NotificationKind.FREE_NOW.value, owner=user_id, entity_id=boundary_id, occurred_at=now),
                now,
            ))
        elif state.activity.type == ActivityType.EXAM or state.exam:
            exam_state = (state.exam or {}).get("state", "in_progress")
            if exam_state in ("break", "between_exams"):
                kind = NotificationKind.EXAM_BREAK.value
            elif exam_state == "in_progress":
                kind = NotificationKind.EXAM_STARTED.value
            elif exam_state == "finished":
                kind = NotificationKind.EXAM_FINISHED.value
            else:
                kind = NotificationKind.EXAM_BREAK.value
            delivered_count += len(await process_event(
                db,
                DomainEvent(kind=kind, owner=user_id, entity_id=boundary_id, occurred_at=now),
                now,
            ))
        elif state.activity.layer == 5:
            delivered_count += len(await process_event(
                db,
                DomainEvent(kind=NotificationKind.ACTIVITY_STARTED.value, owner=user_id, entity_id=boundary_id, occurred_at=now),
                now,
            ))

    # Evaluate expired manual activities and prompt owner
    expired_activities = await db.activities.find({
        "owner": user_id,
        "status": {"$in": ["ACTIVE", "CHANGED", "EXTENDED"]},
        "expected_end_at": {"$lte": now},
    }).to_list(length=10)
    for exp_act in expired_activities:
        cur_v = exp_act.get("version", 1)
        await db.activities.update_one(
            {"_id": exp_act["_id"], "version": cur_v},
            {"$set": {"status": "EXPIRED", "version": cur_v + 1, "updated_at": now}},
        )
        nudge_id = f"expired-prompt:{exp_act['_id']}"
        if not await db.notifications.find_one({"_id": nudge_id}):
            owner_nudge = {
                "_id": nudge_id,
                "to": user_id,
                "about_owner": user_id,
                "kind": NotificationKind.ACTIVITY_EXTENDED.value,
                "payload_redacted": {"text": f"Your activity '{exp_act.get('title', 'Activity')}' has ended. Extend or finish?"},
                "action": "NONE",
                "dedupe_key": nudge_id,
                "status": "pending",
                "owner_only": True,
                "created_at": now,
            }
            await db.notifications.insert_one(owner_nudge)
            notification_broker.publish(user_id, owner_nudge)
            delivered_count += 1

    return delivered_count


@activity.defn
async def nudge_owner(activity_id: str) -> None:
    _tag_activity_scope()
    db = get_db()
    activity_record = await db.activities.find_one({"_id": activity_id})
    if not activity_record:
        return
    now = get_clock().now()
    notification_id = f"arrival-nudge:{activity_id}"
    if await db.notifications.find_one({"_id": notification_id}):
        return
    notification = {
        "_id": notification_id,
        "to": activity_record["owner"],
        "about_owner": activity_record["owner"],
        "kind": NotificationKind.ARRIVAL_MISSING.value,
        "payload_redacted": {"text": "Did you arrive?"},
        "action": "NONE",
        "dedupe_key": notification_id,
        "status": "pending",
        "owner_only": True,
        "created_at": now,
    }
    await db.notifications.insert_one(notification)
    notification_broker.publish(activity_record["owner"], notification)


@activity.defn
async def notify_arrival_missing(activity_id: str) -> int:
    _tag_activity_scope()
    db = get_db()
    activity_record = await db.activities.find_one({"_id": activity_id})
    if not activity_record:
        return 0
    now = get_clock().now()
    return len(await process_event(
        db,
        DomainEvent(
            kind=NotificationKind.ARRIVAL_MISSING.value,
            owner=activity_record["owner"],
            entity_id=activity_id,
            occurred_at=now,
        ),
        now,
    ))


@activity.defn
async def mark_all_clear(activity_id: str) -> int:
    _tag_activity_scope()
    db = get_db()
    activity_record = await db.activities.find_one({"_id": activity_id})
    if not activity_record:
        return 0
    now = get_clock().now()
    return len(await process_event(
        db,
        DomainEvent(
            kind=NotificationKind.ALL_CLEAR.value,
            owner=activity_record["owner"],
            entity_id=activity_id,
            occurred_at=now,
        ),
        now,
    ))


@activity.defn
async def check_and_notify_promise(message_id: str) -> int:
    _tag_activity_scope()
    db = get_db()
    message = await db.messages.find_one({"_id": message_id})
    if not message or message.get("promise_done_at"):
        return 0

    now = get_clock().now()
    dedupe_key = f"promise-due:{message_id}"
    if await db.notifications.find_one({"_id": dedupe_key}):
        return 0

    await db.messages.update_one(
        {"_id": message_id},
        {"$set": {"call_pending": True}},
    )

    notification = {
        "_id": dedupe_key,
        "to": message["owner"],
        "about_owner": message["owner"],
        "kind": NotificationKind.PROMISE_DUE.value,
        "payload_redacted": {"text": "A promised call is due"},
        "action": "MESSAGE",
        "dedupe_key": dedupe_key,
        "status": "pending",
        "owner_only": True,
        "created_at": now,
    }
    await db.notifications.insert_one(notification)
    notification_broker.publish(message["owner"], notification)
    return 1