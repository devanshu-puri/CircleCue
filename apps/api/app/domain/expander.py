"""Template expansion: turns stored templates + exceptions into a flat list of Segments for a given date.
Pure function, no I/O.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

from app.domain.freewindows import Segment


WEEK_A_ISO_ANCHOR = date(2024, 1, 1)   # ISO week 1 of 2024 is Week-A


def _is_week_a(d: date) -> bool:
    """True if `d` falls in an A-week (odd ISO week number)."""
    return (d.isocalendar()[1] % 2) == 1


def _to_utc(time_str: str, d: date, tz: str) -> datetime:
    """Parse 'HH:MM' + date + tz → UTC-aware datetime."""
    h, m = int(time_str[:2]), int(time_str[3:5])
    local_dt = datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(tz))
    return local_dt.astimezone(timezone.utc)


def _active_on(template: Dict[str, Any], occurrence_date: date) -> bool:
    active_from = template.get("active_from")
    active_to = template.get("active_to")
    for value, is_start in ((active_from, True), (active_to, False)):
        if value is None:
            continue
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        bound_date = value.date() if isinstance(value, datetime) else value
        if is_start and occurrence_date < bound_date:
            return False
        if not is_start and occurrence_date > bound_date:
            return False
    return True


def _previous_overnight_segments(
    templates: List[Dict[str, Any]],
    exceptions: List[Dict[str, Any]],
    target_date: date,
    tz: str,
) -> List[Segment]:
    previous_date = target_date - timedelta(days=1)
    target_start = _to_utc("00:00", target_date, tz)
    segments = []

    for template in templates:
        start_str = template["start_local"]
        end_str = template["end_local"]
        if end_str > start_str:
            continue
        if previous_date.weekday() not in template.get("days", list(range(7))):
            continue
        week_pattern = template.get("week_pattern", "every")
        if week_pattern == "A" and not _is_week_a(previous_date):
            continue
        if week_pattern == "B" and _is_week_a(previous_date):
            continue
        if not _active_on(template, previous_date):
            continue

        template_id = str(template.get("_id") or template.get("id", ""))
        matching = [
            item for item in exceptions
            if item.get("date") == previous_date.isoformat()
            and item.get("template_id") in (None, template_id)
        ]
        if any(item.get("kind") in ("day_off", "cancelled") for item in matching):
            continue
        exception = matching[0] if matching else None
        if exception:
            kind = exception.get("kind")
            if kind == "moved":
                start_str = exception.get("new_start") or start_str
                end_str = exception.get("new_end") or end_str
            elif kind in ("extended", "early_end"):
                end_str = exception.get("new_end") or end_str

        try:
            start = _to_utc(start_str, previous_date, tz)
            end = _to_utc(end_str, previous_date, tz)
        except (TypeError, ValueError):
            continue
        if end <= start:
            end += timedelta(days=1)
        if start < target_start < end:
            availability = template.get("availability", {})
            segments.append(Segment(
                start=start,
                end=end,
                activity_type=template.get("activity_type", "CLASS"),
                label=template.get("title", "Busy"),
                calls_ok=availability.get("calls", "ok") == "ok",
                visibility=template.get("visibility"),
                call_preference=availability.get("calls", "ok"),
            ))

    return segments


def expand(
    templates: List[Dict[str, Any]],
    exceptions: List[Dict[str, Any]],
    exam_sets: List[Dict[str, Any]],
    target_date: date,
    tz: str,
) -> List[Segment]:
    """
    Expand templates for target_date into Segments, applying exceptions and exam overrides.
    Returns segments sorted by start time.
    """
    iso_day = target_date.weekday()  # 0 = Monday

    # --- EXAM OVERRIDE ---
    exam_set = next(
        (e for e in exam_sets if e.get("date") == target_date.isoformat()),
        None
    )

    # Build exception lookup keyed by template_id (or None for day exceptions)
    exceptions_by_tid: Dict[Optional[str], Dict[str, Any]] = {}
    day_off = False
    for exc in exceptions:
        if exc.get("date") == target_date.isoformat():
            if exc.get("kind") == "day_off":
                day_off = True
            else:
                tid = exc.get("template_id")
                exceptions_by_tid[tid] = exc

    segments: List[Segment] = _previous_overnight_segments(
        templates, exceptions, target_date, tz
    )
    if day_off:
        return segments

    # --- EXAM SET ITEMS (overrides schedule unless keep_schedule=True) ---
    if exam_set:
        keep_schedule = exam_set.get("keep_schedule", False)
        pre_buf = exam_set.get("pre_buffer_min", 30)
        post_buf = exam_set.get("post_buffer_min", 15)

        for item in exam_set.get("items", []):
            start = _to_utc(item["start_local"], target_date, tz)
            end = _to_utc(item["end_local"], target_date, tz)

            if item["type"] == "exam":
                # Pre-buffer: BUSY slot
                segments.append(Segment(
                    start=start - timedelta(minutes=pre_buf),
                    end=start,
                    activity_type="EXAM",
                    label=f"Pre-exam buffer ({item.get('subject','Exam')})",
                    calls_ok=False,
                    call_preference="no",
                ))
                segments.append(Segment(
                    start=start,
                    end=end,
                    activity_type="EXAM",
                    label=item.get("subject", "Exam"),
                    calls_ok=False,
                    call_preference="no",
                ))
                # Post-buffer
                segments.append(Segment(
                    start=end,
                    end=end + timedelta(minutes=post_buf),
                    activity_type="EXAM",
                    label="Post-exam buffer",
                    calls_ok=False,
                    call_preference="no",
                ))
            else:
                # break
                calls_ok = item.get("calls_ok", False)
                segments.append(Segment(
                    start=start,
                    end=end,
                    activity_type="BREAK",
                    label="Exam break",
                    calls_ok=calls_ok,
                    call_preference="ok" if calls_ok else "no",
                ))

        if not keep_schedule:
            return sorted(segments, key=lambda s: s.start)

    # --- SCHEDULE TEMPLATES ---
    for tmpl in templates:
        if not _active_on(tmpl, target_date):
            continue

        days = tmpl.get("days", list(range(7)))
        if iso_day not in days:
            continue

        wp = tmpl.get("week_pattern", "every")
        if wp == "A" and not _is_week_a(target_date):
            continue
        if wp == "B" and _is_week_a(target_date):
            continue

        tid = str(tmpl.get("_id") or tmpl.get("id", ""))
        exc = exceptions_by_tid.get(tid)

        if exc:
            kind = exc["kind"]
            if kind == "cancelled":
                continue
            elif kind == "moved":
                start_str = exc.get("new_start") or tmpl["start_local"]
                end_str = exc.get("new_end") or tmpl["end_local"]
            elif kind == "extended":
                start_str = tmpl["start_local"]
                end_str = exc.get("new_end") or tmpl["end_local"]
            elif kind == "early_end":
                start_str = tmpl["start_local"]
                end_str = exc.get("new_end") or tmpl["end_local"]
            else:
                start_str = tmpl["start_local"]
                end_str = tmpl["end_local"]
        else:
            start_str = tmpl["start_local"]
            end_str = tmpl["end_local"]

        try:
            start = _to_utc(start_str, target_date, tz)
            end = _to_utc(end_str, target_date, tz)
            if end <= start:
                end += timedelta(days=1)
        except Exception:
            continue

        avail = tmpl.get("availability", {})
        calls_ok = avail.get("calls", "ok") == "ok"

        segments.append(Segment(
            start=start,
            end=end,
            activity_type=tmpl.get("activity_type", "CLASS"),
            label=tmpl.get("title", "Busy"),
            calls_ok=calls_ok,
            visibility=tmpl.get("visibility"),
            call_preference=avail.get("calls", "ok"),
        ))

    return sorted(segments, key=lambda s: s.start)
