"""
Domain resolver: pure function (user_bundle, now) -> ResolvedState.
No I/O. Implements MEMORY.md §5.2 precedence layers.

Layers (highest wins):
  1. Safety / active context packet
  2. Manual Live Activity / availability override (unexpired)
  3. Active Travel
  4. Exam (date-set)
  5. Scenario-produced activity
  6. Schedule (with exceptions)
  7. Routine baseline
  8. Unknown
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.domain.models import (
    ActivityType, Calls, Messages, Provenance, ProvenanceSource,
    ReachabilityResolved, ResolvedState, ActiveActivityResolved,
    Status, TravelPhase, VisibilitySpec, ContextSnapshot,
)
from app.domain.expander import expand, Segment
from app.domain.freewindows import free_windows, free_in_minutes
from app.domain.scenarios import resolve_time_scenarios

# ── Default activity durations (minutes) ──────────────────────────────────────
DEFAULT_DURATIONS: Dict[str, int] = {
    "STUDY": 60, "MEAL": 30, "MEETING": 60, "GYM": 60,
    "SLEEP": 480, "SOCIAL": 90, "PERSONAL": 60, "CUSTOM": 60,
    "WORK": 480, "CLASS": 60, "LAB": 120, "EXAM": 180,
}

STALE_SNAPSHOT_HOURS = 3  # badge snapshot as "may be outdated"
logger = logging.getLogger("circlecue.resolver")


@dataclass
class UserBundle:
    """All data needed for a single resolve() call — caller fetches, resolver stays pure."""
    owner_id: str
    tz: str
    routine_prefs: Dict[str, Any]
    sharing_paused: Dict[str, Any]

    # lists of raw dicts from DB
    activities: List[Dict[str, Any]] = field(default_factory=list)
    templates: List[Dict[str, Any]] = field(default_factory=list)
    exceptions: List[Dict[str, Any]] = field(default_factory=list)
    exam_sets: List[Dict[str, Any]] = field(default_factory=list)
    phone_state: Optional[Dict[str, Any]] = None
    scenarios: List[Dict[str, Any]] = field(default_factory=list)


def _is_expired(act: Dict[str, Any], now: datetime) -> bool:
    end = act.get("expected_end_at")
    if isinstance(end, str):
        end = datetime.fromisoformat(end)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return bool(end and now >= end and act.get("status") not in (
        Status.COMPLETED.value, Status.CANCELLED.value, Status.EXPIRED.value
    ))


def _dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    if isinstance(val, str):
        dt = datetime.fromisoformat(val)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return None


def _active_manual(activities: List[Dict], now: datetime) -> Optional[Dict]:
    """Return the most recent ACTIVE/EXTENDED manual live activity that isn't expired."""
    live_types = {
        "STUDY", "SLEEP", "WORK", "MEETING", "GYM", "SOCIAL",
        "FAMILY", "BUSY", "PERSONAL", "CUSTOM", "MEAL",
    }
    candidates = [
        a for a in activities
        if a.get("type") in live_types
            and a.get("status") in (
                Status.ACTIVE.value, Status.EXTENDED.value,
                Status.DELAYED.value, Status.CHANGED.value,
            )
        and a.get("provenance", {}).get("source") != ProvenanceSource.SYSTEM_INFERRED.value
        and not _is_expired(a, now)
    ]
    return max(candidates, key=lambda a: _dt(a["start_at"]) or now, default=None)


def _active_travel(activities: List[Dict], now: datetime) -> Optional[Dict]:
    candidates = [
        activity for activity in activities
        if activity.get("type") == ActivityType.TRAVEL.value
            and activity.get("status") in (
                Status.ACTIVE.value, Status.EXTENDED.value,
                Status.DELAYED.value, Status.CHANGED.value,
            )
        and not _is_expired(activity, now)
    ]
    return max(candidates, key=lambda activity: _dt(activity.get("start_at")) or now, default=None)


def _active_safety(activities: List[Dict], now: datetime) -> Optional[Dict]:
    candidates = [
        activity for activity in activities
        if activity.get("type") == ActivityType.SAFETY.value
        and activity.get("status") in (Status.ACTIVE.value, Status.EXTENDED.value)
        and not _is_expired(activity, now)
    ]
    return max(candidates, key=lambda activity: _dt(activity.get("start_at")) or now, default=None)


def _scenario_activity(activities: List[Dict], now: datetime) -> Optional[Dict]:
    candidates = [
        activity for activity in activities
        if activity.get("provenance", {}).get("source") == ProvenanceSource.SYSTEM_INFERRED.value
        and activity.get("status") in (Status.ACTIVE.value, Status.EXTENDED.value)
        and not _is_expired(activity, now)
    ]
    return max(candidates, key=lambda activity: _dt(activity.get("start_at")) or now, default=None)


def _phone_staleness(phone: Optional[Dict], now: datetime) -> bool:
    if not phone:
        return False
    updated = _dt(phone.get("updated_at"))
    return bool(updated and (now - updated).total_seconds() > STALE_SNAPSHOT_HOURS * 3600)


def _last_shared_context(phone: Optional[Dict]) -> Optional[ContextSnapshot]:
    if not phone:
        return None
    context = phone.get("last_shared_context")
    if isinstance(context, ContextSnapshot):
        return context
    if not isinstance(context, dict):
        return None
    shared_at = _dt(context.get("shared_at"))
    snapshot = context.get("snapshot")
    if shared_at is None or not isinstance(snapshot, dict):
        return None
    return ContextSnapshot(snapshot=snapshot, shared_at=shared_at)


def _next_state_boundary(
    now: datetime,
    phone: Optional[Dict],
    *candidates: Optional[datetime],
) -> Optional[datetime]:
    boundaries = [value for value in candidates if value is not None and value > now]
    updated_at = _dt(phone.get("updated_at")) if phone else None
    if updated_at:
        boundaries.append(updated_at + timedelta(hours=STALE_SNAPSHOT_HOURS))
    context = _last_shared_context(phone)
    if context:
        boundaries.append(context.shared_at + timedelta(hours=STALE_SNAPSHOT_HOURS))
    return min((value for value in boundaries if value > now), default=None)


def _segment_at(segments: List[Segment], now: datetime) -> Optional[Segment]:
    active = [seg for seg in segments if seg.start <= now < seg.end]
    if len(active) > 1:
        logger.warning("Overlapping schedule segments detected; count=%d", len(active))
    return max(active, key=lambda seg: seg.start, default=None)


def _next_boundary(segments: List[Segment], now: datetime) -> Optional[datetime]:
    boundaries = [
        boundary
        for seg in segments
        for boundary in (seg.start, seg.end)
        if boundary > now
    ]
    return min(boundaries, default=None)


def _reachability_from_activity(act: Dict, phone: Optional[Dict]) -> ReachabilityResolved:
    avail = act.get("availability", {})
    calls = Calls(avail.get("calls", Calls.OK.value))
    messages = Messages(avail.get("messages", Messages.OK.value))

    # Phone overrides
    if phone:
        if phone.get("declared_offline"):
            calls = Calls.NO
            messages = Messages.LATER
        elif phone.get("calls") == Calls.NO.value:
            calls = Calls.NO

    end = _dt(act.get("expected_end_at"))
    return ReachabilityResolved(
        calls=calls,
        messages=messages,
        reason=act.get("title"),
        until=end,
    )


def resolve(bundle: UserBundle, now: datetime) -> ResolvedState:
    """Pure function: (UserBundle, now) -> ResolvedState. No I/O."""
    tz = bundle.tz or "UTC"
    pause_until = _dt(bundle.sharing_paused.get("until"))
    sharing_paused_active = bool(
        bundle.sharing_paused.get("active", False)
        and (pause_until is None or pause_until > now)
    )

    # Phone state snapshot
    phone = bundle.phone_state
    phone_projection: Dict[str, Any] = {}
    if phone:
        phone_projection = {
            "mode": phone.get("mode", "normal"),
            "battery_pct": phone.get("battery_pct", 100),
            "battery_bucket": phone.get("battery_bucket", "ok"),
            "may_go_offline": phone.get("may_go_offline", False),
            "declared_offline": phone.get("declared_offline", False),
            "stale": _phone_staleness(phone, now),
        }

    def next_boundary(*candidates: Optional[datetime]) -> Optional[datetime]:
        return _next_state_boundary(
            now, phone, pause_until, scenario_boundary, *candidates
        )

    scenario_from_dsl, scenario_boundary = resolve_time_scenarios(
        bundle.scenarios, now, tz
    )

    # ── Layer 1: Safety ───────────────────────────────────────────────────────
    safety = _active_safety(bundle.activities, now)
    if safety:
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType.SAFETY,
                label=safety.get("title", "Safety alert"),
                until=_dt(safety.get("expected_end_at")),
                layer=1,
                provenance=Provenance(source=ProvenanceSource.USER_SHARED),
                visibility=VisibilitySpec.model_validate(safety.get("visibility") or {}),
            ),
            reachability=ReachabilityResolved(calls=Calls.NO, messages=Messages.OK),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(_dt(safety.get("expected_end_at"))),
        )

    # ── Layer 2: Manual Live Activity ─────────────────────────────────────────
    manual = _active_manual(bundle.activities, now)
    if manual:
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType(manual["type"]),
                label=manual.get("title", manual["type"].capitalize()),
                until=_dt(manual.get("expected_end_at")),
                layer=2,
                provenance=Provenance(
                    source=ProvenanceSource(manual.get("provenance", {}).get("source", ProvenanceSource.USER_SHARED.value))
                ),
                visibility=VisibilitySpec.model_validate(manual.get("visibility") or {}),
            ),
            reachability=_reachability_from_activity(manual, phone),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(_dt(manual.get("expected_end_at"))),
        )

    # ── Layer 3: Active Travel ────────────────────────────────────────────────
    travel = _active_travel(bundle.activities, now)
    if travel:
        meta = travel.get("metadata", {})
        eta = _dt(meta.get("eta"))
        overdue = bool(eta and now > eta and travel.get("phase") != TravelPhase.ARRIVED.value)
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType.TRAVEL,
                label=travel.get("title", "Travelling"),
                until=eta,
                layer=3,
                provenance=Provenance(source=ProvenanceSource.USER_SHARED),
                visibility=VisibilitySpec.model_validate(travel.get("visibility") or {}),
            ),
            reachability=ReachabilityResolved(
                calls=Calls.PREFER_NOT,
                messages=Messages.OK,
                reason="Travelling",
                until=eta,
            ),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(
                eta, _dt(travel.get("expected_end_at"))
            ),
            travel={
                "destination": meta.get("destination", ""),
                "destination_kind": meta.get("destination_kind", "other"),
                "eta": eta.isoformat() if eta else None,
                "phase": travel.get("phase", TravelPhase.PLANNED.value),
                "overdue": overdue,
                "companions": meta.get("companions", []),
                "vehicle_number": meta.get("vehicle_number"),
                "driver_name": meta.get("driver_name"),
                "driver_phone": meta.get("driver_phone"),
                "mode": meta.get("mode", "cab"),
            },
        )

    # ── Layer 4: Exam Set ─────────────────────────────────────────────────────
    today_str = now.astimezone(ZoneInfo(tz)).date().isoformat()
    exam_set = next(
        (e for e in bundle.exam_sets if e.get("date") == today_str), None
    )
    if exam_set:
        segs = expand([], [], [exam_set], now.astimezone(ZoneInfo(tz)).date(), tz)
        current_seg = _segment_at(segs, now)
        if current_seg:
            act_type = ActivityType(current_seg.activity_type) if current_seg.activity_type in ActivityType.__members__ else ActivityType.EXAM
            calls = Calls(current_seg.call_preference)
            exams_today = sum(
                1 for item in exam_set.get("items", [])
                if item.get("type") == "exam"
            )
            return ResolvedState(
                owner=bundle.owner_id,
                as_of=now,
                sharing_paused=sharing_paused_active,
                activity=ActiveActivityResolved(
                    type=act_type,
                    label=current_seg.label,
                    until=current_seg.end,
                    layer=4,
                    provenance=Provenance(source=ProvenanceSource.USER_SHARED),
                ),
                reachability=ReachabilityResolved(
                    calls=calls,
                    messages=Messages.OK,
                    reason=current_seg.label,
                    until=current_seg.end,
                ),
                phone=phone_projection,
                last_shared_context=_last_shared_context(phone),
                next_boundary_at=next_boundary(current_seg.end),
                exam={
                    "state": "in_progress" if act_type == ActivityType.EXAM else "break",
                    "subject": current_seg.label,
                    "until": current_seg.end.isoformat(),
                    "exams_today": exams_today,
                },
            )

        if exam_set and not exam_set.get("keep_schedule", False) and segs:
            exam_items = [
                item for item in exam_set.get("items", [])
                if item.get("type") == "exam"
            ]
            exams_today = len(exam_items)
            first_segment = min(segs, key=lambda segment: segment.start)
            last_segment_end = max(segment.end for segment in segs)
            next_segment = next((segment for segment in segs if segment.start > now), None)

            if now < first_segment.start:
                subject = exam_items[0].get("subject", "Exam") if exam_items else "Exam"
                state_name = "upcoming"
                until = first_segment.start
                calls = Calls.OK
            elif now >= last_segment_end:
                subject = exam_items[-1].get("subject", "Exam") if exam_items else "Exam"
                state_name = "finished"
                until = None
                calls = Calls.OK
            elif next_segment:
                subject = next_segment.label
                state_name = "between_exams"
                until = next_segment.start
                calls = Calls.PREFER_NOT
            else:
                subject = "Exam"
                state_name = "between_exams"
                until = last_segment_end
                calls = Calls.PREFER_NOT

            return ResolvedState(
                owner=bundle.owner_id,
                as_of=now,
                sharing_paused=sharing_paused_active,
                activity=ActiveActivityResolved(
                    type=ActivityType.EXAM,
                    label=subject,
                    until=until,
                    layer=4,
                    provenance=Provenance(source=ProvenanceSource.USER_SHARED),
                ),
                reachability=ReachabilityResolved(
                    calls=calls,
                    messages=Messages.OK,
                    reason=subject,
                    until=until,
                ),
                phone=phone_projection,
                last_shared_context=_last_shared_context(phone),
                next_boundary_at=next_boundary(
                    first_segment.start if state_name == "upcoming" else until,
                ),
                exam={
                    "state": state_name,
                    "subject": subject,
                    "until": until.isoformat() if until else None,
                    "exams_today": exams_today,
                },
            )

    # ── Layer 5: Scenario Activity ────────────────────────────────────────────
    scenario_act = _scenario_activity(bundle.activities, now) or scenario_from_dsl
    if scenario_act:
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType(scenario_act["type"]),
                label=scenario_act.get("title", "Busy"),
                until=_dt(scenario_act.get("expected_end_at")),
                layer=5,
                provenance=Provenance(source=ProvenanceSource.SYSTEM_INFERRED),
                visibility=VisibilitySpec.model_validate(scenario_act.get("visibility") or {}),
            ),
            reachability=_reachability_from_activity(scenario_act, phone),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(
                _dt(scenario_act.get("expected_end_at"))
            ),
        )

    # ── Layer 6: Schedule ─────────────────────────────────────────────────────
    local_date = now.astimezone(ZoneInfo(tz)).date()
    segments = expand(bundle.templates, bundle.exceptions, bundle.exam_sets, local_date, tz)
    current_seg = _segment_at(segments, now)

    routine = bundle.routine_prefs or {}
    min_window = routine.get("min_call_window_min", 10)
    buffer = routine.get("buffer_min", 5)
    day_start_str = routine.get("wake", "07:00")
    day_end_str = routine.get("sleep", "23:00")

    try:
        from zoneinfo import ZoneInfo as ZI
        local_now = now.astimezone(ZI(tz))
        day_start = datetime(local_now.year, local_now.month, local_now.day,
                             int(day_start_str[:2]), int(day_start_str[3:5]),
                             tzinfo=ZI(tz)).astimezone(timezone.utc)
        day_end = datetime(local_now.year, local_now.month, local_now.day,
                           int(day_end_str[:2]), int(day_end_str[3:5]),
                           tzinfo=ZI(tz)).astimezone(timezone.utc)
    except Exception:
        day_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        day_end = now.replace(hour=23, minute=0, second=0, microsecond=0)

    if current_seg:
        act_type_str = current_seg.activity_type
        calls = Calls(current_seg.call_preference)
        next_b = _next_boundary(segments, now)
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType(act_type_str) if act_type_str in ActivityType.__members__ else ActivityType.BUSY,
                label=current_seg.label,
                until=current_seg.end,
                layer=6,
                provenance=Provenance(source=ProvenanceSource.USER_SHARED),
                visibility=VisibilitySpec.model_validate(current_seg.visibility or {}),
            ),
            reachability=ReachabilityResolved(
                calls=calls,
                messages=Messages.OK,
                reason=current_seg.label,
                until=current_seg.end,
            ),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(next_b),
        )

    # Between schedule segments → free window
    windows = free_windows(segments, day_start, day_end, min_window, buffer)
    free_now = bool(segments) and any(w.start <= now < w.end for w in windows)
    if free_now:
        current_window = next(w for w in windows if w.start <= now < w.end)
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType.FREE,
                label=f"Free (~{current_window.net_minutes} min)",
                until=current_window.end,
                layer=6,
                provenance=Provenance(source=ProvenanceSource.SYSTEM_INFERRED),
            ),
            reachability=ReachabilityResolved(
                calls=Calls.OK,
                messages=Messages.OK,
                until=current_window.end,
                free_in_min=current_window.net_minutes,
            ),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(current_window.end),
        )

    # ── Layer 7: Routine baseline ─────────────────────────────────────────────
    if day_start <= now < day_end:
        return ResolvedState(
            owner=bundle.owner_id,
            as_of=now,
            sharing_paused=sharing_paused_active,
            activity=ActiveActivityResolved(
                type=ActivityType.FREE,
                label="Free",
                until=day_end,
                layer=7,
                provenance=Provenance(source=ProvenanceSource.SYSTEM_INFERRED),
            ),
            reachability=ReachabilityResolved(calls=Calls.OK, messages=Messages.OK),
            phone=phone_projection,
            last_shared_context=_last_shared_context(phone),
            next_boundary_at=next_boundary(day_end),
        )

    # ── Layer 8: Unknown ──────────────────────────────────────────────────────
    return ResolvedState(
        owner=bundle.owner_id,
        as_of=now,
        sharing_paused=sharing_paused_active,
        activity=None,
        reachability=ReachabilityResolved(calls=Calls.OK, messages=Messages.OK),
        phone=phone_projection,
        last_shared_context=_last_shared_context(phone),
        next_boundary_at=next_boundary(
            day_start if day_start > now else day_start + timedelta(days=1)
        ),
    )
