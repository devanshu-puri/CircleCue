"""Tests for connection reminders and pickup predictor (M09)."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.domain.models import NotificationKind
from app.domain.reminders import evaluate_connection_reminders
from app.predict.pickup import PickupPredictor, predict_pickup_probability


@pytest.mark.asyncio
async def test_evaluate_connection_reminders_triggers_when_due(mock_db):
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    owner_id = "user-arjun"
    target_id = "user-priya"

    # Seed target user
    await mock_db.users.insert_one({"_id": target_id, "name": "Priya Singh"})

    # Seed high-importance connection plan
    plan_id = "plan-1"
    await mock_db.connection_plans.insert_one({
        "_id": plan_id,
        "owner": owner_id,
        "target": target_id,
        "importance": "high",
        "rule": "weekly",
        "last_connected_at": (now - timedelta(days=8)).isoformat(),
        "snoozed_until": None,
        "cooldown_min": 1440,
        "nudges_today": 0,
    })

    notifications = await evaluate_connection_reminders(mock_db, owner_id, now)
    assert len(notifications) == 1
    assert notifications[0]["kind"] == NotificationKind.CONNECTION_REMINDER.value
    assert notifications[0]["to"] == owner_id
    assert "Priya Singh" in notifications[0]["payload_redacted"]["text"]

    # Plan should have nudges_today updated
    updated_plan = await mock_db.connection_plans.find_one({"_id": plan_id})
    assert updated_plan["nudges_today"] == 1

    # Second check right away generates 0 because dedupe / check
    second_check = await evaluate_connection_reminders(mock_db, owner_id, now)
    assert len(second_check) == 0


@pytest.mark.asyncio
async def test_evaluate_connection_reminders_respects_snooze_and_importance(mock_db):
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    owner_id = "user-arjun"

    # Snoozed plan
    await mock_db.connection_plans.insert_one({
        "_id": "plan-snoozed",
        "owner": owner_id,
        "target": "user-priya",
        "importance": "high",
        "rule": "weekly",
        "last_connected_at": (now - timedelta(days=10)).isoformat(),
        "snoozed_until": (now + timedelta(days=1)).isoformat(),
        "nudges_today": 0,
    })

    # Normal importance plan
    await mock_db.connection_plans.insert_one({
        "_id": "plan-normal",
        "owner": owner_id,
        "target": "user-priya",
        "importance": "normal",
        "rule": "weekly",
        "last_connected_at": (now - timedelta(days=10)).isoformat(),
        "nudges_today": 0,
    })

    notifications = await evaluate_connection_reminders(mock_db, owner_id, now)
    assert len(notifications) == 0


@pytest.mark.asyncio
async def test_evaluate_connection_reminders_caps_at_two_nudges(mock_db):
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    owner_id = "user-arjun"

    await mock_db.connection_plans.insert_one({
        "_id": "plan-maxed",
        "owner": owner_id,
        "target": "user-priya",
        "importance": "high",
        "rule": "daily",
        "last_connected_at": (now - timedelta(days=2)).isoformat(),
        "last_nudge_at": now.isoformat(),
        "nudges_today": 2,
    })

    notifications = await evaluate_connection_reminders(mock_db, owner_id, now)
    assert len(notifications) == 0


def test_pickup_predictor_heuristics():
    predictor = PickupPredictor(provider="stub")

    # High probability case: reachability ok, daytime, full battery
    high_score = predictor.predict({
        "reachability_calls": "ok",
        "battery_bucket": "ok",
        "phone_mode": "normal",
        "local_hour": 14,
    })
    assert high_score >= 0.70

    # Low probability case: reachability no
    no_score = predictor.predict({
        "reachability_calls": "no",
        "battery_bucket": "ok",
    })
    assert no_score <= 0.10

    # Critical battery / night case
    night_score = predictor.predict({
        "reachability_calls": "ok",
        "battery_bucket": "critical",
        "phone_mode": "dnd",
        "local_hour": 3,
    })
    assert night_score <= 0.30


def test_reminders_router_api():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Reminders User",
        "email": "reminders-user@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    # 1. Create a plan
    res = client.post(
        "/reminders/plans",
        json={"target": "user-priya", "importance": "high", "rule": "weekly"},
    )
    assert res.status_code == 201
    plan = res.json()
    plan_id = plan["_id"]

    # 2. List plans
    list_res = client.get("/reminders/plans")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Snooze plan
    snooze_res = client.post(
        f"/reminders/plans/{plan_id}/snooze",
        json={"days": 5},
    )
    assert snooze_res.status_code == 200
    assert snooze_res.json()["status"] == "snoozed"

    # 4. Mark connected
    conn_res = client.post(
        f"/reminders/plans/{plan_id}/connected",
    )
    assert conn_res.status_code == 200
    assert conn_res.json()["status"] == "connected"

    # 5. Check reminders endpoint
    check_res = client.post("/reminders/check")
    assert check_res.status_code == 200
    assert "evaluated_count" in check_res.json()

    # 6. Predict pickup endpoint
    pred_res = client.post(
        "/predict/pickup",
        json={"reachability_calls": "ok", "local_hour": 15},
    )
    assert pred_res.status_code == 200
    assert 0.0 <= pred_res.json()["probability"] <= 1.0
