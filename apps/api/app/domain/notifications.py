"""Deterministic notification policy and rendering from redacted viewer state."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import asyncio
import logging
import sentry_sdk
from zoneinfo import ZoneInfo

from app.domain.models import (
    AccessLevel, CardKey, Grant, NotificationKind, ViewerState,
)
from app.domain.events import DomainEvent
from app.domain.events import publish
from app.domain.scenarios import resolve_time_scenarios
from app.domain.visibility import can_view, can_view_for_connection, state_for_viewer, viewers_for

logger = logging.getLogger("circlecue.notifications")


@dataclass(frozen=True)
class NotificationPolicy:
    card: Optional[CardKey]
    required_level: AccessLevel
    notify_flag: Optional[str] = None
    quiet_hours_bypass: bool = False
    owner_only: bool = False


NOTIFICATION_POLICIES = {
    NotificationKind.FREE_NOW: NotificationPolicy(CardKey.SCHEDULE, AccessLevel.STATUS, "free_now"),
    NotificationKind.EXAM_STARTED: NotificationPolicy(CardKey.EXAM, AccessLevel.STATUS, "exam"),
    NotificationKind.EXAM_BREAK: NotificationPolicy(CardKey.EXAM, AccessLevel.STATUS, "exam"),
    NotificationKind.EXAM_FINISHED: NotificationPolicy(CardKey.EXAM, AccessLevel.STATUS, "exam"),
    NotificationKind.CLASS_CANCELLED: NotificationPolicy(CardKey.SCHEDULE, AccessLevel.STATUS, "schedule_change"),
    NotificationKind.SCHEDULE_CHANGED: NotificationPolicy(CardKey.SCHEDULE, AccessLevel.STATUS, "schedule_change"),
    NotificationKind.ACTIVITY_STARTED: NotificationPolicy(CardKey.LIVE, AccessLevel.STATUS, "activity"),
    NotificationKind.ACTIVITY_EXTENDED: NotificationPolicy(CardKey.LIVE, AccessLevel.STATUS, "activity"),
    NotificationKind.TRAVEL_STARTED: NotificationPolicy(CardKey.TRAVEL, AccessLevel.STATUS, "travel"),
    NotificationKind.TRAVEL_DELAYED: NotificationPolicy(CardKey.TRAVEL, AccessLevel.STATUS, "travel"),
    NotificationKind.PLAN_CHANGED: NotificationPolicy(CardKey.TRAVEL, AccessLevel.STATUS, "travel"),
    NotificationKind.TRAVEL_ARRIVED: NotificationPolicy(CardKey.TRAVEL, AccessLevel.STATUS, "travel"),
    NotificationKind.BATTERY_LOW: NotificationPolicy(CardKey.PHONE, AccessLevel.STATUS, "battery"),
    NotificationKind.BATTERY_CRITICAL: NotificationPolicy(CardKey.PHONE, AccessLevel.STATUS, "battery"),
    NotificationKind.PHONE_MAY_GO_OFFLINE: NotificationPolicy(CardKey.PHONE, AccessLevel.STATUS, "battery"),
    NotificationKind.MESSAGE_DROP: NotificationPolicy(CardKey.MESSAGE, AccessLevel.DETAILS, "message"),
    NotificationKind.ARRIVAL_MISSING: NotificationPolicy(CardKey.SAFETY, AccessLevel.STATUS, "safety", True),
    NotificationKind.ALL_CLEAR: NotificationPolicy(CardKey.SAFETY, AccessLevel.STATUS, "safety", True),
    NotificationKind.PROMISE_DUE: NotificationPolicy(CardKey.MESSAGE, AccessLevel.DETAILS, "message"),
    NotificationKind.URGENT_OVERRIDE: NotificationPolicy(CardKey.SAFETY, AccessLevel.STATUS, "safety", True),
    NotificationKind.CONNECTION_REMINDER: NotificationPolicy(None, AccessLevel.NONE, owner_only=True),
}


@dataclass(frozen=True)
class RenderedNotification:
    text: str
    action: str


def notification_policy(kind: NotificationKind) -> NotificationPolicy:
    return NOTIFICATION_POLICIES[kind]


def should_notify(kind: NotificationKind, grant: Optional[Grant], now: datetime) -> bool:
    policy = notification_policy(kind)
    if policy.owner_only or policy.card is None:
        return False
    if not can_view(grant, policy.card, policy.required_level, now):
        return False
    if policy.notify_flag and not getattr(grant.notify, policy.notify_flag, False):
        return False
    return True


def render_notification(kind: NotificationKind, state: ViewerState) -> RenderedNotification:
    if state.sharing_paused:
        return RenderedNotification("Sharing paused", "NONE")
    if kind == NotificationKind.ARRIVAL_MISSING:
        return RenderedNotification("Arrival confirmation is missing", "MESSAGE")
    if kind == NotificationKind.ALL_CLEAR:
        return RenderedNotification("Arrival confirmed. All good.", "NONE")

    activity = state.activity or {}
    label = activity.get("label") or "Status updated"
    calls = getattr(state.reachability, "calls", None)
    messages = getattr(state.reachability, "messages", None)
    action = "CALL" if getattr(calls, "value", calls) == "ok" else (
        "MESSAGE" if getattr(messages, "value", messages) == "ok" else "NONE"
    )

    if kind == NotificationKind.FREE_NOW:
        free_minutes = getattr(state.reachability, "free_in_min", None)
        duration = f" for about {free_minutes} minutes" if free_minutes else ""
        return RenderedNotification(f"Free{duration}. Call?", action)
    if kind in (NotificationKind.EXAM_STARTED, NotificationKind.EXAM_BREAK, NotificationKind.EXAM_FINISHED):
        return RenderedNotification(label, action)
    if kind in (
        NotificationKind.TRAVEL_STARTED,
        NotificationKind.TRAVEL_DELAYED,
        NotificationKind.PLAN_CHANGED,
        NotificationKind.TRAVEL_ARRIVED,
    ):
        travel = state.travel or {}
        destination = travel.get("destination")
        companions = travel.get("companions")
        details = f" to {destination}" if destination else ""
        if companions:
            details += f" with {', '.join(companions)}"
        eta = travel.get("eta")
        eta_text = f" ETA {eta}" if eta else ""
        return RenderedNotification(f"{label}{details}.{eta_text}".strip(), action)
    if kind in (NotificationKind.BATTERY_LOW, NotificationKind.BATTERY_CRITICAL, NotificationKind.PHONE_MAY_GO_OFFLINE):
        bucket = (state.phone or {}).get("battery_bucket", "")
        suffix = f" Battery: {bucket}." if bucket else ""
        if state.last_shared_context and state.last_shared_context.shared_at:
            time_str = state.last_shared_context.shared_at.strftime("%I:%M %p").lstrip("0")
            suffix += f" (Last shared {time_str})"
        return RenderedNotification(f"Phone status updated.{suffix}".strip(), action)
    if kind == NotificationKind.MESSAGE_DROP:
        return RenderedNotification("You received a message", "MESSAGE")
    if kind == NotificationKind.PROMISE_DUE:
        return RenderedNotification("A promised call is due", "MESSAGE")
    if kind == NotificationKind.CONNECTION_REMINDER:
        return RenderedNotification("Time to catch up with a friend", "CALL")
    return RenderedNotification(label, action)


class NotificationBroker:
    def __init__(self):
        self._subscribers: Dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, viewer_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(viewer_id, set()).add(queue)
        return queue

    def unsubscribe(self, viewer_id: str, queue: asyncio.Queue) -> None:
        self._subscribers.get(viewer_id, set()).discard(queue)
        if not self._subscribers.get(viewer_id):
            self._subscribers.pop(viewer_id, None)

    def publish(self, viewer_id: str, notification: Dict[str, Any]) -> None:
        for queue in self._subscribers.get(viewer_id, set()):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(notification)


notification_broker = NotificationBroker()


async def publish_and_process(db, event: DomainEvent, now: datetime) -> List[Dict[str, Any]]:
    publish(event)
    delivered = await process_event(db, event, now)
    await _evaluate_event_scenarios(db, event, now)
    await _signal_temporal(db, event)
    return delivered


async def _evaluate_event_scenarios(db, event: DomainEvent, now: datetime) -> None:
    if event.kind in ("SCENARIO_CHANGED",):
        return

    scenarios = await db.scenarios.find({"owner": event.owner, "enabled": True}).to_list(length=200)
    if not scenarios:
        return

    # 1. Activity state triggers
    if event.kind in ("ACTIVITY_STARTED", "ACTIVITY_EXTENDED"):
        activity = await db.activities.find_one({"_id": event.entity_id, "owner": event.owner})
        if activity and activity.get("provenance", {}).get("source") != "system_inferred":
            act_type = activity.get("type")
            start_at = activity.get("start_at") or now
            for scenario in scenarios:
                trigger = scenario.get("trigger", {})
                if trigger.get("kind") == "activity_state" and trigger.get("activity_type") == act_type:
                    elapsed_min = trigger.get("elapsed_min", 0)
                    if (now - start_at).total_seconds() >= elapsed_min * 60:
                        for effect in scenario.get("effects", []):
                            if effect.get("kind") == "set_activity":
                                from bson import ObjectId
                                new_act_id = str(ObjectId())
                                await db.activities.insert_one({
                                    "_id": new_act_id,
                                    "owner": event.owner,
                                    "type": effect.get("activity_type", "CUSTOM"),
                                    "title": effect.get("title", scenario.get("name")),
                                    "status": "ACTIVE",
                                    "start_at": now,
                                    "expected_end_at": now + timedelta(hours=1),
                                    "availability": effect.get("availability", {}),
                                    "visibility": effect.get("visibility", {}),
                                    "provenance": {"source": "system_inferred", "model": "scenario_engine"},
                                    "scenario_id": str(scenario["_id"]),
                                    "version": 1,
                                    "created_at": now,
                                    "updated_at": now,
                                })
                                await publish_and_process(db, DomainEvent(
                                    kind="SCENARIO_CHANGED",
                                    owner=event.owner,
                                    entity_id=str(scenario["_id"]),
                                    after={"triggered_by": event.kind},
                                    occurred_at=now,
                                ), now)

    # 2. Battery triggers
    elif event.kind in ("BATTERY_LOW", "BATTERY_CRITICAL", "PHONE_STATE_CHANGED"):
        phone = await db.phone_state.find_one({"_id": event.owner})
        battery_pct = phone.get("battery_pct") if phone else None
        if battery_pct is not None:
            for scenario in scenarios:
                trigger = scenario.get("trigger", {})
                if trigger.get("kind") == "battery":
                    threshold = trigger.get("threshold_pct", 0)
                    if battery_pct <= threshold:
                        for effect in scenario.get("effects", []):
                            if effect.get("kind") == "set_activity":
                                from bson import ObjectId
                                new_act_id = str(ObjectId())
                                await db.activities.insert_one({
                                    "_id": new_act_id,
                                    "owner": event.owner,
                                    "type": effect.get("activity_type", "CUSTOM"),
                                    "title": effect.get("title", scenario.get("name")),
                                    "status": "ACTIVE",
                                    "start_at": now,
                                    "expected_end_at": now + timedelta(hours=1),
                                    "availability": effect.get("availability", {}),
                                    "visibility": effect.get("visibility", {}),
                                    "provenance": {"source": "system_inferred", "model": "scenario_engine"},
                                    "scenario_id": str(scenario["_id"]),
                                    "version": 1,
                                    "created_at": now,
                                    "updated_at": now,
                                })
                                await publish_and_process(db, DomainEvent(
                                    kind="SCENARIO_CHANGED",
                                    owner=event.owner,
                                    entity_id=str(scenario["_id"]),
                                    after={"triggered_by": event.kind},
                                    occurred_at=now,
                                ), now)


async def _signal_temporal(db, event: DomainEvent) -> None:
    from app.config import settings

    if not settings.TEMPORAL_ENABLED:
        return
    try:
        from app.workflows.client import (
            signal_arrival_watch,
            signal_timeline_changed,
            start_arrival_watch,
        )
        from app.workflows.inputs import ArrivalWatchInput

        await signal_timeline_changed(event.owner)
        if event.kind == "TRAVEL_STARTED":
            activity_record = await db.activities.find_one({
                "_id": event.entity_id,
                "owner": event.owner,
            })
            if not activity_record:
                return
            check = activity_record.get("check_on_me") or {}
            if not check.get("enabled"):
                return
            metadata = activity_record.get("metadata") or {}
            eta = metadata.get("eta") or activity_record.get("expected_end_at")
            if not eta:
                return
            offline_window = metadata.get("expected_offline_window") or {}
            await start_arrival_watch(ArrivalWatchInput(
                activity_id=event.entity_id,
                owner_id=event.owner,
                eta=eta.isoformat() if isinstance(eta, datetime) else str(eta),
                grace_min=check.get("grace_min", 15),
                escalate_min=check.get("escalate_min", 15),
                expected_offline_until=(
                    offline_window.get("end").isoformat()
                    if isinstance(offline_window.get("end"), datetime)
                    else offline_window.get("end")
                ),
            ))
        elif event.kind in ("TRAVEL_DELAYED", "PLAN_CHANGED", "TRAVEL_ARRIVED", "ACTIVITY_CANCELLED"):
            activity_record = await db.activities.find_one({
                "_id": event.entity_id,
                "owner": event.owner,
            })
            if event.kind == "TRAVEL_ARRIVED":
                await signal_arrival_watch(event.entity_id, "arrived")
            elif event.kind == "ACTIVITY_CANCELLED":
                await signal_arrival_watch(event.entity_id, "cancel")
            elif activity_record:
                eta = (activity_record.get("metadata") or {}).get("eta")
                if eta:
                    eta_text = eta.isoformat() if isinstance(eta, datetime) else str(eta)
                    signal = "delay" if event.kind == "TRAVEL_DELAYED" else "plan_changed"
                    await signal_arrival_watch(event.entity_id, signal, eta_text)
        elif event.kind == "MESSAGE_DROP":
            message = await db.messages.find_one({
                "_id": event.entity_id,
                "owner": event.owner,
            })
            if message and message.get("promise_at"):
                promise_at = message["promise_at"]
                promise_at_str = (
                    promise_at.isoformat()
                    if isinstance(promise_at, datetime)
                    else str(promise_at)
                )
                from app.workflows.client import start_promise_watch
                await start_promise_watch(event.entity_id, promise_at_str)
        elif event.kind in ("MESSAGE_REACTION", "MESSAGE_DONE"):
            from app.workflows.client import signal_promise_done
            await signal_promise_done(event.entity_id)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.warning(
            "Temporal trigger unavailable; resolver state remains authoritative",
            extra={"owner_id": event.owner, "workflow_event": event.kind, "error_type": type(exc).__name__},
        )
        try:
            await db.users.update_one({"_id": event.owner}, {"$set": {"needs_resync": True}})
        except Exception:
            pass


def _inside_quiet_hours(now: datetime, tz: str, routine: Dict[str, Any]) -> bool:
    local = now.astimezone(ZoneInfo(tz))
    sleep = routine.get("sleep", "23:00")
    wake = routine.get("wake", "07:00")
    sleep_minute = int(sleep[:2]) * 60 + int(sleep[3:5])
    wake_minute = int(wake[:2]) * 60 + int(wake[3:5])
    current_minute = local.hour * 60 + local.minute
    if sleep_minute <= wake_minute:
        return sleep_minute <= current_minute < wake_minute
    return current_minute >= sleep_minute or current_minute < wake_minute


async def process_event(db, event: DomainEvent, now: datetime) -> List[Dict[str, Any]]:
    """Persist and deliver one event through the grant-aware notification path."""
    try:
        kind = NotificationKind(event.kind)
    except ValueError:
        return []
    policy = notification_policy(kind)
    if policy.owner_only or policy.card is None:
        return []

    owner = await db.users.find_one({"_id": event.owner}) or {}
    owner_tz = owner.get("tz", "UTC")
    scenarios = await db.scenarios.find({"owner": event.owner, "enabled": True}).to_list(length=200)
    active_scenario, _ = resolve_time_scenarios(scenarios, now, owner_tz)
    if active_scenario:
        if active_scenario.get("notification_rule") in ("never", "only_if_called"):
            return []
        scenario_effects = active_scenario.get("scenario_effects", [])
        suppressed_kinds = {
            kind
            for effect in scenario_effects
            if effect.get("kind") == "suppress_notifications"
            for kind in effect.get("kinds", [])
        }
        if kind.value in suppressed_kinds or "*" in suppressed_kinds:
            return []

    viewer_ids = await viewers_for(db, event.owner, policy.card, policy.required_level, now)
    if kind == NotificationKind.MESSAGE_DROP:
        message = await db.messages.find_one({
            "_id": event.entity_id,
            "owner": event.owner,
        })
        if not message:
            return []
        audience = set(message.get("audience", []))
        viewer_ids = [viewer_id for viewer_id in viewer_ids if viewer_id in audience]
    if active_scenario:
        scenario_audience = set(active_scenario.get("audience", []))
        audience_mode = active_scenario.get("audience_mode", "all_granted")
        if audience_mode == "only":
            viewer_ids = [viewer_id for viewer_id in viewer_ids if viewer_id in scenario_audience]
        elif audience_mode == "except":
            viewer_ids = [viewer_id for viewer_id in viewer_ids if viewer_id not in scenario_audience]
    delivered: List[Dict[str, Any]] = []

    for viewer_id in viewer_ids:
        grant_doc = await db.grants.find_one({"owner": event.owner, "viewer": viewer_id})
        grant = Grant.model_validate(grant_doc) if grant_doc else None
        if not should_notify(kind, grant, now):
            continue

        viewer = await db.users.find_one({"_id": viewer_id}) or {}
        if not policy.quiet_hours_bypass and _inside_quiet_hours(
            now, viewer.get("tz", "UTC"), viewer.get("routine_prefs", {})
        ):
            continue

        if not policy.quiet_hours_bypass:
            recent = await db.notifications.find({"to": viewer_id}).to_list(length=5000)
            day_ago = now - timedelta(days=1)
            if sum(
                1 for item in recent
                if item.get("about_owner") == event.owner
                and item.get("created_at") is not None
                and item["created_at"] >= day_ago
            ) >= 2:
                continue

        window = event.occurred_at.strftime("%Y%m%d%H")
        dedupe_key = f"{event.owner}:{viewer_id}:{kind.value}:{event.entity_id}:{window}"
        if await db.notifications.find_one({"dedupe_key": dedupe_key}):
            continue

        viewer_state = await state_for_viewer(db, event.owner, viewer_id, now)
        if not viewer_state:
            continue
        rendered = render_notification(kind, viewer_state)
        notification = {
            "_id": f"{dedupe_key}",
            "to": viewer_id,
            "about_owner": event.owner,
            "kind": kind.value,
            "payload_redacted": {"text": rendered.text},
            "action": rendered.action,
            "dedupe_key": dedupe_key,
            "status": "pending",
            "created_at": now,
        }
        await db.notifications.insert_one(notification)

        # Revocation can happen between candidate selection and delivery.
        if not await can_view_for_connection(
            db, event.owner, viewer_id, policy.card, policy.required_level, now
        ):
            await db.notifications.update_one(
                {"_id": notification["_id"], "to": viewer_id},
                {"$set": {"status": "suppressed"}},
            )
            continue

        latest_state = await state_for_viewer(db, event.owner, viewer_id, now)
        if not latest_state or latest_state.sharing_paused:
            await db.notifications.update_one(
                {"_id": notification["_id"], "to": viewer_id},
                {"$set": {"status": "suppressed"}},
            )
            continue

        notification_broker.publish(viewer_id, notification)
        delivered.append(notification)
    return delivered
