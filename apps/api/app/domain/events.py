"""In-process event bus used by the lifecycle service → notification pipeline subscribes in M08."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class DomainEvent:
    kind: str           # e.g. "ACTIVITY_STARTED"
    owner: str
    entity_id: str
    occurred_at: datetime
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None


_handlers: List[Callable[[DomainEvent], None]] = []


def subscribe(handler: Callable[[DomainEvent], None]) -> None:
    _handlers.append(handler)


def publish(event: DomainEvent) -> None:
    for h in _handlers:
        h(event)
