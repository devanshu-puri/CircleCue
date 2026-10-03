from datetime import datetime, timezone, timedelta
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime:
        """Returns current aware UTC datetime."""
        ...

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class DemoClock:
    def __init__(self, initial_offset: timedelta = timedelta(seconds=0)):
        self._offset: timedelta = initial_offset

    def now(self) -> datetime:
        return datetime.now(timezone.utc) + self._offset

    def set_offset(self, offset: timedelta) -> None:
        self._offset = offset

    def advance(self, delta: timedelta) -> None:
        self._offset += delta

    def reset(self) -> None:
        self._offset = timedelta(seconds=0)

# Singleton global instance used across app & background workers
_global_clock: Clock = SystemClock()

def get_clock() -> Clock:
    return _global_clock

def set_global_clock(clock: Clock) -> None:
    global _global_clock
    _global_clock = clock
