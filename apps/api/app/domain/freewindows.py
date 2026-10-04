"""Free-window computation. Pure functions, no I/O."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Segment:
    """A named time block on a day's timeline."""
    start: datetime          # UTC-aware
    end: datetime            # UTC-aware
    activity_type: str       # ActivityType value as string
    label: str
    calls_ok: bool = True    # whether free-window qualifies as callable
    visibility: Optional[Dict[str, Any]] = None
    call_preference: str = "ok"


@dataclass(frozen=True)
class Window:
    """A contiguous free window."""
    start: datetime
    end: datetime
    net_minutes: int         # after subtracting buffer


def free_windows(
    segments: List[Segment],
    day_start: datetime,
    day_end: datetime,
    min_window_min: int = 10,
    buffer_min: int = 5,
) -> List[Window]:
    """
    Given a list of busy Segments for a day, compute free windows >= min_window_min
    after subtracting the per-side buffer.

    segments must be sorted by start. day_start/day_end define the search horizon.
    """
    busy = sorted(segments, key=lambda s: s.start)
    gaps: List[tuple[datetime, datetime]] = []

    cursor = day_start
    for seg in busy:
        seg_start = max(seg.start, day_start)
        seg_end = min(seg.end, day_end)
        if seg_start > cursor:
            gaps.append((cursor, seg_start))
        cursor = max(cursor, seg_end)

    if cursor < day_end:
        gaps.append((cursor, day_end))

    windows = []
    for gap_start, gap_end in gaps:
        raw_min = int((gap_end - gap_start).total_seconds() / 60)
        net_min = raw_min - buffer_min
        if net_min >= min_window_min:
            windows.append(Window(
                start=gap_start,
                end=gap_end,
                net_minutes=net_min,
            ))
    return windows


def free_in_minutes(windows: List[Window], now: datetime) -> Optional[int]:
    """Returns minutes until the next free window, or None if one is active."""
    for w in windows:
        if w.start <= now < w.end:
            return 0  # currently free
        if w.start > now:
            return int((w.start - now).total_seconds() / 60)
    return None
