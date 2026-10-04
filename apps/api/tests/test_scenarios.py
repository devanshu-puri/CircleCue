from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.domain.scenarios import ScenarioDefinition, resolve_time_scenarios


def _scenario(scenario_id, *, priority=50, days=None, calls="ok", start="19:00", end="22:00"):
    return {
        "_id": scenario_id,
        "owner": "owner-1",
        "name": scenario_id,
        "enabled": True,
        "priority": priority,
        "trigger": {
            "kind": "time",
            "days": days if days is not None else [5],
            "start_local": start,
            "end_local": end,
        },
        "effects": [{
            "kind": "set_activity",
            "activity_type": "CUSTOM",
            "title": scenario_id,
            "availability": {"calls": calls},
        }],
    }


def test_scenario_dsl_rejects_invalid_weekday_and_time():
    scenario = _scenario("bad-time")
    scenario["trigger"]["days"] = [7]

    with pytest.raises(ValidationError):
        ScenarioDefinition.model_validate(scenario)


def test_active_scenario_conflict_prefers_priority_then_restrictiveness():
    now = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)
    winner, _ = resolve_time_scenarios([
        _scenario("higher-priority", priority=80, calls="prefer_not"),
        _scenario("lower-priority", priority=50, calls="no"),
    ], now, "Asia/Kolkata")

    assert winner["title"] == "higher-priority"

    restrictive, _ = resolve_time_scenarios([
        _scenario("reachable", calls="ok"),
        _scenario("unavailable", calls="no"),
    ], now, "Asia/Kolkata")

    assert restrictive["title"] == "unavailable"


def test_upcoming_scenario_returns_start_as_next_boundary():
    now = datetime(2026, 10, 3, 12, 30, tzinfo=timezone.utc)
    active, boundary = resolve_time_scenarios(
        [_scenario("evening", start="19:00", end="22:00")],
        now,
        "Asia/Kolkata",
    )

    assert active is None
    assert boundary == datetime(2026, 10, 3, 13, 30, tzinfo=timezone.utc)


def test_scenario_crud_version_and_dry_run_grant_intersection():
    owner = TestClient(app)
    viewer = TestClient(app)
    owner_data = owner.post("/auth/register", json={
        "name": "Scenario Owner",
        "email": "scenario-owner@example.com",
        "password": "password123",
    }).json()
    viewer_data = viewer.post("/auth/register", json={
        "name": "Scenario Viewer",
        "email": "scenario-viewer@example.com",
        "password": "password123",
    }).json()
    request = owner.post("/connections/request", json={"user_code": viewer_data["user_code"]})
    viewer.post(f"/connections/{request.json()['id']}/accept")
    now = datetime.fromisoformat(owner.get("/readyz").json()["clock_now"])

    created = owner.post("/scenarios", json={
        "name": "Weekly cricket",
        "trigger": {
            "kind": "time",
            "days": [now.weekday()],
            "start_local": "19:00",
            "end_local": "22:00",
        },
        "effects": [{
            "kind": "set_activity",
            "activity_type": "CUSTOM",
            "title": "Cricket",
            "availability": {"calls": "no"},
        }],
        "audience": [viewer_data["id"]],
        "audience_mode": "only",
    })
    assert created.status_code == 201
    scenario_id = created.json()["_id"]

    preview = owner.post(f"/scenarios/{scenario_id}/dry-run")
    assert preview.status_code == 200
    assert preview.json()["audience"] == []
    assert any("no matching grant" in warning for warning in preview.json()["warnings"])

    updated = owner.patch(f"/scenarios/{scenario_id}", json={
        "name": "Paused cricket",
        "enabled": False,
        "trigger": created.json()["trigger"],
        "effects": created.json()["effects"],
        "audience": [viewer_data["id"]],
        "audience_mode": "only",
        "version": 1,
    })
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = owner.patch(f"/scenarios/{scenario_id}", json={
        "name": "Stale",
        "enabled": True,
        "trigger": created.json()["trigger"],
        "effects": created.json()["effects"],
        "version": 1,
    })
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_activity_state_trigger_fires_on_activity_started(mock_db):
    from app.domain.events import DomainEvent
    from app.domain.notifications import publish_and_process

    owner_id = "user-scenario-owner"
    now = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)

    # Setup scenario with ActivityStateTrigger
    await mock_db.scenarios.insert_one({
        "_id": "scenario-gym-mode",
        "owner": owner_id,
        "name": "Gym Focus",
        "enabled": True,
        "trigger": {
            "kind": "activity_state",
            "activity_type": "GYM",
            "elapsed_min": 0,
        },
        "effects": [{
            "kind": "set_activity",
            "activity_type": "CUSTOM",
            "title": "Gym Focus Mode",
            "availability": {"calls": "no", "messages": "later"},
        }],
    })

    # Insert started activity
    act_id = "act-gym-1"
    await mock_db.activities.insert_one({
        "_id": act_id,
        "owner": owner_id,
        "type": "GYM",
        "title": "Working Out",
        "status": "ACTIVE",
        "start_at": now,
        "provenance": {"source": "user_shared"},
    })

    # Fire event
    await publish_and_process(mock_db, DomainEvent(
        kind="ACTIVITY_STARTED",
        owner=owner_id,
        entity_id=act_id,
        occurred_at=now,
    ), now)

    # Verify inferred activity created by scenario
    inferred = await mock_db.activities.find_one({
        "owner": owner_id,
        "provenance.source": "system_inferred",
    })
    assert inferred is not None
    assert inferred["title"] == "Gym Focus Mode"
    assert inferred["availability"]["calls"] == "no"


@pytest.mark.asyncio
async def test_battery_trigger_fires_at_threshold(mock_db):
    from app.domain.events import DomainEvent
    from app.domain.notifications import publish_and_process

    owner_id = "user-battery-owner"
    now = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)

    # Setup battery trigger scenario
    await mock_db.scenarios.insert_one({
        "_id": "scenario-low-bat",
        "owner": owner_id,
        "name": "Low Battery Silence",
        "enabled": True,
        "trigger": {
            "kind": "battery",
            "threshold_pct": 10,
        },
        "effects": [{
            "kind": "set_activity",
            "activity_type": "CUSTOM",
            "title": "Phone Dying — Going Dark",
            "availability": {"calls": "no", "messages": "later"},
        }],
    })

    # Set phone state to 8%
    await mock_db.phone_state.insert_one({
        "_id": owner_id,
        "battery_pct": 8,
        "mode": "silent",
    })

    # Fire event
    await publish_and_process(mock_db, DomainEvent(
        kind="BATTERY_LOW",
        owner=owner_id,
        entity_id=owner_id,
        occurred_at=now,
    ), now)

    # Verify inferred activity created by battery trigger
    inferred = await mock_db.activities.find_one({
        "owner": owner_id,
        "provenance.source": "system_inferred",
    })
    assert inferred is not None
    assert inferred["title"] == "Phone Dying — Going Dark"