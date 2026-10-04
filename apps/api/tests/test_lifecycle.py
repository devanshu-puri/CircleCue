from datetime import datetime, timezone, timedelta

import pytest

from app.domain.models import Status, TravelPhase, ActivityType
from app.domain.lifecycle import can_transition, can_transition_travel_phase
from app.domain.lifecycle_service import default_expected_end, transition
from app.domain.events import DomainEvent, publish
from app.core.errors import StateConflictError

def test_generic_status_transitions():
    assert can_transition(ActivityType.STUDY, Status.PLANNED, Status.ACTIVE) is True
    assert can_transition(ActivityType.STUDY, Status.PLANNED, Status.CANCELLED) is True
    assert can_transition(ActivityType.STUDY, Status.ACTIVE, Status.COMPLETED) is True
    assert can_transition(ActivityType.STUDY, Status.ACTIVE, Status.EXTENDED) is True
    assert can_transition(ActivityType.STUDY, Status.ACTIVE, Status.EXPIRED) is True

def test_invalid_status_transitions():
    # Terminal states cannot transition out
    assert can_transition(ActivityType.STUDY, Status.COMPLETED, Status.ACTIVE) is False
    assert can_transition(ActivityType.STUDY, Status.CANCELLED, Status.ACTIVE) is False
    assert can_transition(ActivityType.STUDY, Status.EXPIRED, Status.ACTIVE) is False

def test_travel_phase_transitions():
    assert can_transition_travel_phase(TravelPhase.PLANNED, TravelPhase.TRAVELLING) is True
    assert can_transition_travel_phase(TravelPhase.TRAVELLING, TravelPhase.ARRIVED) is True
    assert can_transition_travel_phase(TravelPhase.ARRIVED, TravelPhase.COMPLETED) is True
    assert can_transition_travel_phase(TravelPhase.COMPLETED, TravelPhase.TRAVELLING) is False


def test_transition_extends_and_emits_event(monkeypatch):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    activity = {
        "_id": "activity-1", "owner": "owner-1", "type": "STUDY",
        "status": Status.ACTIVE.value,
        "expected_end_at": now + timedelta(minutes=15), "version": 2,
    }
    emitted = []
    monkeypatch.setattr("app.domain.lifecycle_service.publish", emitted.append)

    updated = transition(
        activity,
        Status.EXTENDED,
        actor="owner-1",
        payload={"extend_min": 20},
        now=now,
    )

    assert updated["expected_end_at"] == activity["expected_end_at"] + timedelta(minutes=20)
    assert updated["version"] == 3
    assert updated["updated_at"] == now
    assert emitted[0].kind == "ACTIVITY_EXTENDED"
    assert emitted[0].owner == "owner-1"


def test_transition_change_applies_typed_fields(monkeypatch):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    monkeypatch.setattr("app.domain.lifecycle_service.publish", lambda event: None)
    activity = {
        "_id": "activity-2", "owner": "owner-1", "type": "STUDY",
        "status": Status.ACTIVE.value, "title": "Old title", "version": 1,
    }

    updated = transition(
        activity,
        Status.CHANGED,
        actor="owner-1",
        payload={"title": "Updated title", "availability": {"calls": "no"}},
        now=now,
    )

    assert updated["title"] == "Updated title"
    assert updated["availability"] == {"calls": "no"}


def test_transition_rejects_invalid_change(monkeypatch):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    monkeypatch.setattr("app.domain.lifecycle_service.publish", lambda event: None)
    activity = {
        "_id": "activity-3", "owner": "owner-1", "type": "STUDY",
        "status": Status.COMPLETED.value,
    }

    with pytest.raises(StateConflictError):
        transition(activity, Status.ACTIVE, actor="owner-1", now=now)


def test_event_bus_propagates_handler_failure(monkeypatch):
    import app.domain.events as events

    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)

    def fail_handler(event):
        raise RuntimeError("subscriber failed")

    monkeypatch.setattr(events, "_handlers", [fail_handler])
    event = DomainEvent("ACTIVITY_STARTED", "owner-1", "activity-1", now)

    with pytest.raises(RuntimeError, match="subscriber failed"):
        publish(event)


def test_default_expected_end_uses_duration_and_routine_wake():
    start_at = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    wake_at = datetime(2026, 10, 4, 1, tzinfo=timezone.utc)

    assert default_expected_end(ActivityType.STUDY, start_at) == start_at + timedelta(minutes=60)
    assert default_expected_end(ActivityType.SLEEP, start_at, wake_at) == wake_at
