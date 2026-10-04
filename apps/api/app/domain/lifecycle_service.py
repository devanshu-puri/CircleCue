"""Lifecycle service: validates transitions and emits DomainEvents."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.domain.models import Status, TravelPhase, ActivityType
from app.domain.lifecycle import can_transition, can_transition_travel_phase
from app.domain.events import DomainEvent, publish
from app.core.errors import StateConflictError

# Default durations in minutes
DEFAULT_DURATIONS: Dict[str, int] = {
    "STUDY": 60, "MEAL": 30, "MEETING": 60, "GYM": 60,
    "SLEEP": 480, "SOCIAL": 90, "PERSONAL": 60, "CUSTOM": 60,
    "WORK": 480, "CLASS": 60, "LAB": 120, "EXAM": 180,
}

# Notification event kinds to emit per transition
TRANSITION_EVENT_MAP: Dict[tuple, str] = {
    (Status.PLANNED.value, Status.ACTIVE.value): "ACTIVITY_STARTED",
    (Status.ACTIVE.value, Status.EXTENDED.value): "ACTIVITY_EXTENDED",
    (Status.ACTIVE.value, Status.DELAYED.value): "ACTIVITY_EXTENDED",
    (Status.ACTIVE.value, Status.COMPLETED.value): "ACTIVITY_COMPLETED",
    (Status.ACTIVE.value, Status.CANCELLED.value): "ACTIVITY_CANCELLED",
    (Status.ACTIVE.value, Status.EXPIRED.value): "ACTIVITY_EXPIRED",
}


def default_expected_end(
    activity_type: ActivityType,
    start_at: datetime,
    routine_wake_at: Optional[datetime] = None,
) -> datetime:
    if activity_type == ActivityType.SLEEP and routine_wake_at and routine_wake_at > start_at:
        return routine_wake_at
    return start_at + timedelta(minutes=DEFAULT_DURATIONS.get(activity_type.value, 60))


def transition(
    activity: Dict[str, Any],
    to_status: Status,
    actor: str,
    now: datetime,
    payload: Optional[Dict[str, Any]] = None,
    publish_event: bool = True,
) -> Dict[str, Any]:
    """
    Validate and apply a lifecycle transition to an activity dict.
    Returns the updated activity dict.
    Raises StateConflictError if the transition is not allowed.
    """
    from_status = Status(activity.get("status", Status.PLANNED.value))
    act_type = ActivityType(activity.get("type", ActivityType.CUSTOM.value))

    if not can_transition(act_type, from_status, to_status):
        raise StateConflictError(
            f"Cannot transition activity from {from_status.value} to {to_status.value}",
            details={"from": from_status.value, "to": to_status.value}
        )

    before = dict(activity)
    updated = dict(activity)
    updated["status"] = to_status.value
    updated["version"] = activity.get("version", 1) + 1
    updated["updated_at"] = now

    if payload:
        for field in (
            "title", "expected_end_at", "availability", "metadata",
            "visibility", "participants", "check_on_me",
        ):
            if field in payload:
                updated[field] = payload[field]

        if "extend_min" in payload:
            end_dt = activity.get("expected_end_at")
            if isinstance(end_dt, str):
                end_dt = datetime.fromisoformat(end_dt)
            if end_dt and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt:
                updated["expected_end_at"] = end_dt + timedelta(minutes=payload["extend_min"])

        if "new_eta" in payload:
            meta = dict(updated.get("metadata", {}))
            meta["eta"] = payload["new_eta"]
            updated["metadata"] = meta
            updated["expected_end_at"] = payload["new_eta"]
            current_phase = TravelPhase(activity.get("phase", TravelPhase.PLANNED.value))
            if not can_transition_travel_phase(current_phase, TravelPhase.DELAYED):
                raise StateConflictError(
                    f"Cannot delay travel from phase {current_phase.value}"
                )
            updated["phase"] = TravelPhase.DELAYED.value

        if "phase" in payload:
            if act_type != ActivityType.TRAVEL:
                raise StateConflictError("Only travel activities have a travel phase")
            phase_val = TravelPhase(payload["phase"])
            if not can_transition_travel_phase(
                TravelPhase(activity.get("phase", TravelPhase.PLANNED.value)),
                phase_val
            ):
                raise StateConflictError(f"Cannot transition travel phase to {phase_val.value}")
            updated["phase"] = phase_val.value

    # Emit domain event
    event_key = (from_status.value, to_status.value)
    event_kind = TRANSITION_EVENT_MAP.get(event_key, f"ACTIVITY_{to_status.value}")
    if publish_event:
        publish(DomainEvent(
            kind=event_kind,
            owner=activity.get("owner", ""),
            entity_id=str(activity.get("_id") or activity.get("id", "")),
            before=before,
            after=updated,
            occurred_at=now,
        ))

    return updated
