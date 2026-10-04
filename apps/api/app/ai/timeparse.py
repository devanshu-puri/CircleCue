"""Resolve model-proposed times deterministically using the owner's timezone."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.ai.schemas import TimeSpec


WEEKDAYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def _target_date(date_ref: str | None, local_now: datetime) -> date:
    if not date_ref or date_ref == "today":
        return local_now.date()
    if date_ref == "tomorrow":
        return local_now.date() + timedelta(days=1)
    if date_ref.startswith("weekday:"):
        weekday = WEEKDAYS.get(date_ref.removeprefix("weekday:").lower()[:3])
        if weekday is None:
            raise ValueError("Unknown weekday in date_ref")
        days_ahead = (weekday - local_now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return local_now.date() + timedelta(days=days_ahead)
    return date.fromisoformat(date_ref)


def resolve_time_spec(spec: TimeSpec, now: datetime, tz: str) -> datetime:
    zone = ZoneInfo(tz)
    aware_now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    local_now = aware_now.astimezone(zone)

    if spec.relative_min is not None:
        return (aware_now + timedelta(minutes=spec.relative_min)).astimezone(timezone.utc)

    if spec.hh_mm is None:
        raise ValueError("TimeSpec must contain hh_mm or relative_min")
    hour_text, _, minute_text = spec.hh_mm.partition(":")
    hour = int(hour_text)
    minute = int(minute_text or "0")
    target_date = _target_date(spec.date_ref, local_now)

    if spec.ampm_assumed and hour <= 12:
        if target_date == local_now.date() and local_now.hour >= 12:
            preferred_hour = hour % 12 + 12
            preferred = datetime.combine(
                target_date,
                time(preferred_hour, minute),
                tzinfo=zone,
            )
            if preferred <= local_now and spec.date_ref in (None, "today"):
                preferred += timedelta(days=1)
            return preferred.astimezone(timezone.utc)
        normalized_hour = hour % 12
        hour_options = sorted({normalized_hour, normalized_hour + 12})
    else:
        hour_options = [hour]

    options = [
        datetime.combine(target_date, time(candidate_hour, minute), tzinfo=zone)
        for candidate_hour in hour_options
    ]
    future_options = [candidate for candidate in options if candidate > local_now]
    if future_options:
        return min(future_options).astimezone(timezone.utc)

    if spec.date_ref in (None, "today") and spec.ampm_assumed:
        next_day_options = [candidate + timedelta(days=1) for candidate in options]
        return min(next_day_options).astimezone(timezone.utc)
    return min(options).astimezone(timezone.utc)