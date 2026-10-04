from datetime import datetime, timezone

import pytest

from app.domain.models import (
    AccessLevel, CardGrants, Grant, NotificationKind, NotifyFlags,
    ReachabilityResolved, ViewerState,
)
from app.domain.notifications import (
    NOTIFICATION_POLICIES,
    notification_broker,
    notification_policy,
    process_event,
    render_notification,
    should_notify,
)
from app.domain.events import DomainEvent
from fastapi.testclient import TestClient
from app.main import app


def test_every_notification_kind_has_one_deterministic_policy():
    assert set(NOTIFICATION_POLICIES) == set(NotificationKind)
    for kind in NotificationKind:
        policy = notification_policy(kind)
        assert policy.card is not None or policy.owner_only


def test_candidate_requires_grant_and_opt_in_flag():
    now = datetime.now(timezone.utc)
    grant = Grant(
        owner="u1",
        viewer="u2",
        cards=CardGrants(schedule=AccessLevel.STATUS),
        notify=NotifyFlags(free_now=False),
    )

    assert should_notify(NotificationKind.FREE_NOW, grant, now) is False
    grant.notify.free_now = True
    assert should_notify(NotificationKind.FREE_NOW, grant, now) is True
    grant.cards.schedule = AccessLevel.NONE
    assert should_notify(NotificationKind.FREE_NOW, grant, now) is False


def test_live_activity_alert_requires_live_access_and_activity_opt_in():
    now = datetime.now(timezone.utc)
    grant = Grant(
        owner="u1",
        viewer="u2",
        cards=CardGrants(live=AccessLevel.STATUS),
        notify=NotifyFlags(activity=False),
    )

    assert should_notify(NotificationKind.ACTIVITY_STARTED, grant, now) is False
    grant.notify.activity = True
    assert should_notify(NotificationKind.ACTIVITY_STARTED, grant, now) is True
    assert should_notify(NotificationKind.ACTIVITY_EXTENDED, grant, now) is True
    grant.cards.live = AccessLevel.NONE
    assert should_notify(NotificationKind.ACTIVITY_STARTED, grant, now) is False


def test_arrival_copy_is_neutral_and_travel_copy_uses_only_projected_fields():
    now = datetime.now(timezone.utc)
    state = ViewerState(
        owner="owner-id",
        as_of=now,
        activity={"type": "TRAVEL", "label": "Travelling", "until": None},
        reachability=ReachabilityResolved(),
        travel={"destination_kind": "home", "eta": "2026-10-03T18:00:00+00:00", "phase": "travelling"},
    )

    travel_copy = render_notification(NotificationKind.TRAVEL_STARTED, state)
    missing_copy = render_notification(NotificationKind.ARRIVAL_MISSING, state)

    assert "destination" not in travel_copy.text.lower()
    assert "running late" not in missing_copy.text.lower()
    assert "confirmation is missing" in missing_copy.text.lower()


@pytest.mark.asyncio
async def test_event_engine_persists_once_for_opted_in_granted_viewer(mock_db):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    mock_db.users.docs["owner"] = {
        "_id": "owner", "name": "Owner Person", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs["viewer"] = {
        "_id": "viewer", "name": "Viewer Person", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "07:00"},
        "sharing_paused": {"active": False},
    }
    await mock_db.connections.insert_one({
        "_id": "connection", "a": "owner", "b": "viewer", "status": "active",
    })
    await mock_db.grants.insert_one({
        "_id": "grant", "owner": "owner", "viewer": "viewer",
        "cards": {"schedule": "status"},
        "notify": {"free_now": True},
        "revoked_at": None,
        "expires_at": None,
    })
    event = DomainEvent("FREE_NOW", "owner", "break-1", occurred_at=now)

    first = await process_event(mock_db, event, now)
    duplicate = await process_event(mock_db, event, now)

    assert len(first) == 1
    assert duplicate == []
    notification = next(iter(mock_db.notifications.docs.values()))
    assert notification["payload_redacted"]["text"] == "Free. Call?"
    assert notification["status"] == "pending"


@pytest.mark.asyncio
async def test_live_activity_start_reaches_viewer_with_activity_opt_in(mock_db):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    mock_db.users.docs["owner"] = {
        "_id": "owner", "name": "Owner Person", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs["viewer"] = {
        "_id": "viewer", "name": "Viewer Person", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "07:00"},
        "sharing_paused": {"active": False},
    }
    await mock_db.connections.insert_one({
        "_id": "connection", "a": "owner", "b": "viewer", "status": "active",
    })
    await mock_db.grants.insert_one({
        "_id": "live-grant", "owner": "owner", "viewer": "viewer",
        "cards": {"live": "status"}, "notify": {"activity": True},
        "revoked_at": None, "expires_at": None,
    })
    await mock_db.activities.insert_one({
        "_id": "study-1", "owner": "owner", "type": "STUDY",
        "title": "Studying until 8", "status": "ACTIVE",
        "start_at": now, "expected_end_at": now.replace(hour=20),
        "availability": {"calls": "no", "messages": "ok"},
        "version": 1, "created_at": now, "updated_at": now,
    })

    delivered = await process_event(
        mock_db, DomainEvent("ACTIVITY_STARTED", "owner", "study-1", now), now
    )

    assert len(delivered) == 1
    assert delivered[0]["to"] == "viewer"
    assert delivered[0]["payload_redacted"]["text"] == "Studying until 8"


@pytest.mark.asyncio
async def test_sse_broker_routes_only_to_subscribed_viewer():
    queue = notification_broker.subscribe("viewer-1")
    notification_broker.publish("viewer-1", {"kind": "FREE_NOW"})

    item = await queue.get()

    assert item == {"kind": "FREE_NOW"}
    notification_broker.unsubscribe("viewer-1", queue)


def test_owner_only_arrival_nudge_is_visible_without_a_self_grant(mock_db):
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Arrival Owner",
        "email": "arrival-owner@example.com",
        "password": "password123",
    })
    owner_id = register.json()["id"]
    mock_db.notifications.docs["arrival-nudge"] = {
        "_id": "arrival-nudge",
        "to": owner_id,
        "about_owner": owner_id,
        "kind": "ARRIVAL_MISSING",
        "owner_only": True,
        "payload_redacted": {"text": "Did you arrive?"},
        "created_at": datetime.now(timezone.utc),
    }

    response = client.get("/notifications")

    assert response.status_code == 200
    assert response.json()[0]["payload_redacted"]["text"] == "Did you arrive?"


@pytest.mark.asyncio
async def test_safety_notifications_bypass_daily_rate_limit(mock_db):
    now = datetime(2026, 10, 3, 15, tzinfo=timezone.utc)
    mock_db.users.docs["owner"] = {
        "_id": "owner", "name": "Owner", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs["viewer"] = {
        "_id": "viewer", "name": "Viewer", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    await mock_db.connections.insert_one({
        "_id": "conn", "a": "owner", "b": "viewer", "status": "active",
    })
    await mock_db.grants.insert_one({
        "_id": "grant", "owner": "owner", "viewer": "viewer",
        "cards": {"safety": "status", "schedule": "status"},
        "notify": {"safety": True, "free_now": True},
        "revoked_at": None, "expires_at": None,
    })
    # Preload 2 notifications in the last 24h
    mock_db.notifications.docs["prev-1"] = {
        "_id": "prev-1", "to": "viewer", "about_owner": "owner", "created_at": now,
    }
    mock_db.notifications.docs["prev-2"] = {
        "_id": "prev-2", "to": "viewer", "about_owner": "owner", "created_at": now,
    }

    # Benign free_now should be rate limited
    free_event = DomainEvent("FREE_NOW", "owner", "free-1", occurred_at=now)
    free_res = await process_event(mock_db, free_event, now)
    assert len(free_res) == 0

    # Safety arrival missing must bypass rate limit
    safety_event = DomainEvent("ARRIVAL_MISSING", "owner", "safety-1", occurred_at=now)
    safety_res = await process_event(mock_db, safety_event, now)
    assert len(safety_res) == 1
    assert safety_res[0]["kind"] == "ARRIVAL_MISSING"


def test_battery_and_reminder_notification_rendering():
    now = datetime(2026, 10, 3, 18, 42, tzinfo=timezone.utc)
    state = ViewerState(
        owner="owner-id",
        as_of=now,
        activity=None,
        reachability=ReachabilityResolved(),
        phone={"battery_bucket": "low"},
        last_shared_context={"snapshot": {}, "shared_at": now},
    )
    rendered_battery = render_notification(NotificationKind.BATTERY_LOW, state)
    assert "Last shared" in rendered_battery.text
    assert "Battery: low" in rendered_battery.text

    reminder = render_notification(NotificationKind.CONNECTION_REMINDER, state)
    assert "catch up" in reminder.text
    assert reminder.action == "CALL"


def test_dev_tick_advances_clock_and_returns_status(mock_db):
    client = TestClient(app)
    response = client.post("/dev/tick", json={"minutes": 15})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["advanced_minutes"] == 15
    assert "now" in data
