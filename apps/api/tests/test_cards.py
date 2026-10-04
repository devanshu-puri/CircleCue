from fastapi.testclient import TestClient

from app.main import app
from app.routers import cards as cards_router


def test_registry_driven_schedule_card_create_and_list():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Card Owner",
        "email": "card-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    created = client.post("/cards/schedule", json={
        "title": "Physics Lecture",
        "activity_type": "CLASS",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
    })

    assert created.status_code == 201
    assert created.json()["card"] == "schedule"
    assert created.json()["record"]["owner"] == register.json()["id"]
    assert created.json()["record"]["kind"] == "SCHEDULE_SLOT"

    listed = client.get("/cards/schedule")
    assert listed.status_code == 200
    assert [record["title"] for record in listed.json()] == ["Physics Lecture"]

    timeline = client.get("/timeline", params={"date": "2026-10-03"})
    assert timeline.status_code == 200
    assert timeline.json()["segments"][0]["label"] == "Physics Lecture"


def test_unknown_card_key_is_rejected():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Card Owner",
        "email": "card-owner-2@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    response = client.get("/cards/not-a-card")

    assert response.status_code == 404


def test_schedule_card_rejects_live_activity_type():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Card Owner",
        "email": "card-owner-3@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    response = client.post("/cards/schedule", json={
        "title": "Studying",
        "activity_type": "STUDY",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
    })

    assert response.status_code == 422


def test_schedule_card_patch_and_delete():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Schedule Owner",
        "email": "schedule-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    created = client.post("/cards/schedule", json={
        "title": "Physics Lecture",
        "activity_type": "CLASS",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
    })
    item_id = created.json()["id"]

    updated = client.patch(f"/cards/schedule/{item_id}", json={
        "version": 1,
        "title": "Physics Lab",
    })
    assert updated.status_code == 200
    assert updated.json()["record"]["title"] == "Physics Lab"
    assert updated.json()["record"]["version"] == 2

    stale = client.patch(f"/cards/schedule/{item_id}", json={
        "version": 1,
        "title": "Stale title",
    })
    assert stale.status_code == 409

    deleted = client.delete(f"/cards/schedule/{item_id}", params={"version": 2})
    assert deleted.status_code == 200
    assert client.get("/cards/schedule").json() == []


def test_live_activity_update_checks_version_and_lifecycle(monkeypatch):
    events = []

    async def capture_event(_db, event, _now):
        events.append(event)
        return []

    monkeypatch.setattr(cards_router, "publish_and_process", capture_event)
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Activity Owner",
        "email": "activity-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    created = client.post("/cards/live", json={
        "type": "STUDY",
        "title": "Revision",
        "availability": {"calls": "no"},
    })
    assert created.status_code == 201
    item_id = created.json()["id"]

    updated = client.patch(f"/cards/live/{item_id}", json={
        "version": 1,
        "title": "Math revision",
    })
    assert updated.status_code == 200
    assert updated.json()["record"]["status"] == "CHANGED"
    assert updated.json()["record"]["version"] == 2
    assert events[-1].kind == "ACTIVITY_EXTENDED"

    stale = client.patch(f"/cards/live/{item_id}", json={
        "version": 1,
        "title": "Stale update",
    })
    assert stale.status_code == 409

    missing_version = client.delete(f"/cards/live/{item_id}")
    assert missing_version.status_code == 422
    stale_delete = client.delete(f"/cards/live/{item_id}", params={"version": 1})
    assert stale_delete.status_code == 409

    cancelled = client.delete(f"/cards/live/{item_id}", params={"version": 2})
    assert cancelled.status_code == 200


def test_owner_can_finish_live_activity_early():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Early Finish Owner",
        "email": "early-finish-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    created = client.post("/cards/live", json={
        "type": "STUDY",
        "title": "Study until 8",
        "expected_end_at": "2099-01-01T20:00:00+00:00",
        "availability": {"calls": "no"},
    })
    assert created.status_code == 201

    finished = client.patch(f"/cards/live/{created.json()['id']}", json={
        "version": 1,
        "status": "COMPLETED",
    })
    assert finished.status_code == 200
    assert finished.json()["record"]["status"] == "COMPLETED"


def test_critical_phone_update_freezes_resolved_context():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Phone Owner",
        "email": "phone-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    response = client.post("/cards/phone", json={
        "battery_pct": 5,
        "may_go_offline": True,
    })

    assert response.status_code == 201
    phone = response.json()["record"]
    assert phone["battery_bucket"] == "dying"
    assert phone["last_shared_context"]["snapshot"]["owner"] == register.json()["id"]
    assert phone["last_shared_context"]["shared_at"]


def test_phone_patch_recomputes_bucket_and_context_snapshot(monkeypatch):
    events = []

    async def capture_event(_db, event, _now):
        events.append(event)
        return []

    monkeypatch.setattr(cards_router, "publish_and_process", capture_event)
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Phone Owner",
        "email": "phone-owner-2@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    owner_id = register.json()["id"]
    created = client.post("/cards/phone", json={"battery_pct": 80})
    assert created.status_code == 201
    assert created.json()["record"]["battery_bucket"] == "ok"
    duplicate = client.post("/cards/phone", json={"battery_pct": 40})
    assert duplicate.status_code == 409

    updated = client.patch(f"/cards/phone/{owner_id}", json={
        "version": 1,
        "battery_pct": 5,
        "may_go_offline": True,
    })

    assert updated.status_code == 200
    assert updated.json()["record"]["battery_bucket"] == "dying"
    assert updated.json()["record"]["last_shared_context"] is not None
    assert updated.json()["record"]["version"] == 2
    assert events[-1].kind == "BATTERY_CRITICAL"


def test_phone_card_is_upserted_on_first_save_then_updated_by_version():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Phone Upsert Owner",
        "email": "phone-upsert-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    owner_id = register.json()["id"]

    created = client.post("/cards/phone", json={"mode": "silent", "battery_pct": 50})
    assert created.status_code == 201
    current = client.get("/cards/phone").json()[0]
    assert current["mode"] == "silent"

    updated = client.patch(f"/cards/phone/{owner_id}", json={
        "version": current["version"],
        "mode": "dnd",
        "battery_pct": 25,
    })
    assert updated.status_code == 200
    assert updated.json()["record"]["mode"] == "dnd"
    assert updated.json()["record"]["battery_pct"] == 25
    assert updated.json()["record"]["version"] == current["version"] + 1


def test_schedule_exception_exam_season_and_message_templates(monkeypatch):
    events = []

    async def capture_event(_db, event, _now):
        events.append(event)
        return []

    monkeypatch.setattr(cards_router, "publish_and_process", capture_event)
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Cards Owner",
        "email": "cards-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    schedule = client.post("/cards/schedule", json={
        "title": "Physics",
        "activity_type": "CLASS",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
    })
    template_id = schedule.json()["id"]

    exception = client.post("/cards/schedule/exceptions", json={
        "template_id": template_id,
        "date": "2026-10-03",
        "kind": "cancelled",
    })
    assert exception.status_code == 201
    assert len(client.get("/cards/schedule/exceptions").json()) == 1

    exam = client.post("/cards/exam", json={
        "date": "2026-10-03",
        "items": [
            {"type": "exam", "subject": "Math", "start_local": "09:00", "end_local": "10:00"},
            {"type": "exam", "subject": "Physics", "start_local": "13:00", "end_local": "14:00"},
        ],
    })
    assert exam.status_code == 201
    exam_id = exam.json()["id"]
    updated_exam = client.post("/cards/exam", json={
        "date": "2026-10-03",
        "version": 1,
        "items": [
            {"type": "exam", "subject": "Math", "start_local": "09:00", "end_local": "10:00"},
        ],
    })
    assert updated_exam.status_code == 201
    assert updated_exam.json()["id"] == exam_id
    assert updated_exam.json()["record"]["version"] == 2
    assert events[-1].kind == "EXAM_SET_CHANGED"
    assert len(client.get("/cards/exam").json()) == 1

    season = client.get("/cards/exam/season")
    assert season.status_code == 200
    assert season.json()["exam_count"] == 1
    assert season.json()["two_exam_days"] == []
    assert client.get("/cards/message/templates").json()


def test_bulk_schedule_save_updates_versions_and_replaces_owner_slots():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Bulk Owner",
        "email": "bulk-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    created = client.post("/cards/schedule", json={
        "title": "Old class",
        "activity_type": "CLASS",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
    })
    record = created.json()["record"]
    response = client.put("/cards/schedule/bulk", json={
        "templates": [{
            "_id": record["_id"],
            "version": record["version"],
            "title": "Updated class",
            "activity_type": "CLASS",
            "days": [5],
            "start_local": "10:00",
            "end_local": "11:00",
        }],
    })

    assert response.status_code == 200
    assert response.json()["templates"][0]["version"] == 2
    assert [slot["title"] for slot in client.get("/cards/schedule").json()] == ["Updated class"]


def test_message_template_applies_text_and_rejects_unconnected_audience():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Message Owner",
        "email": "message-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    unauthorized = client.post("/cards/message", json={
        "template_key": "phone_dying",
        "audience": ["not-connected"],
    })
    assert unauthorized.status_code == 403

    message = client.post("/cards/message", json={"template_key": "phone_dying"})
    assert message.status_code == 201
    assert message.json()["record"]["text"] == "Phone might die"


def test_travel_card_uses_lifecycle_for_departure_and_delay():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Travel Owner",
        "email": "travel-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    created = client.post("/cards/travel", json={
        "type": "TRAVEL",
        "title": "Going home",
        "metadata": {"destination": "Home", "destination_kind": "home"},
    })
    assert created.status_code == 201
    assert created.json()["record"]["status"] == "PLANNED"
    assert created.json()["record"]["phase"] == "planned"
    item_id = created.json()["id"]

    return_prefill = client.get(f"/cards/travel/{item_id}/return")
    assert return_prefill.status_code == 200
    assert return_prefill.json()["metadata"]["destination"] == "Home"
    assert "companions" not in return_prefill.json()["metadata"]

    departed = client.patch(f"/cards/travel/{item_id}", json={
        "version": 1,
        "status": "ACTIVE",
        "phase": "travelling",
    })
    assert departed.status_code == 200
    assert departed.json()["record"]["phase"] == "travelling"

    delayed = client.patch(f"/cards/travel/{item_id}", json={
        "version": 2,
        "new_eta": "2026-10-03T18:00:00+00:00",
    })
    assert delayed.status_code == 200
    assert delayed.json()["record"]["status"] == "CHANGED"
    assert delayed.json()["record"]["phase"] == "delayed"
    assert delayed.json()["record"]["expected_end_at"].startswith("2026-10-03T18:00:00")

    cancelled = client.patch(f"/cards/travel/{item_id}", json={
        "version": 3,
        "status": "CANCELLED",
    })
    assert cancelled.status_code == 200
    assert cancelled.json()["record"]["status"] == "CANCELLED"


def test_travel_card_accepts_and_updates_companion_phone_and_return_time():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Travel Details Owner",
        "email": "travel-details-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    response = client.post("/cards/travel", json={
        "type": "TRAVEL",
        "title": "Going to Baglung",
        "status": "ACTIVE",
        "phase": "travelling",
        "check_on_me": {"enabled": True, "grace_min": 15, "escalate_min": 15},
        "expected_end_at": "2026-10-04T10:00:00+00:00",
        "metadata": {
            "destination": "Baglung",
            "eta": "2026-10-04T10:00:00+00:00",
            "companions": ["Rahul"],
            "companion_phone": "+977 9800000000",
            "expected_return_at": "2026-10-08T10:00:00+00:00",
        },
    })
    assert response.status_code == 201
    record = response.json()["record"]
    assert record["metadata"]["companion_phone"] == "+977 9800000000"
    assert record["metadata"]["expected_return_at"].startswith("2026-10-08")

    updated = client.patch(f"/cards/travel/{response.json()['id']}", json={
        "version": record["version"],
        "check_on_me": {"enabled": False, "grace_min": 10, "escalate_min": 20},
        "metadata": {
            **record["metadata"],
            "companion_phone": "+977 9811111111",
        },
    })
    assert updated.status_code == 200
    assert updated.json()["record"]["metadata"]["companion_phone"] == "+977 9811111111"
    assert updated.json()["record"]["check_on_me"]["enabled"] is False


def test_safety_card_defaults_to_check_on_me():
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Safety Owner",
        "email": "safety-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201

    response = client.post("/cards/safety", json={
        "type": "SAFETY",
        "title": "Check on me",
    })

    assert response.status_code == 201
    assert response.json()["record"]["check_on_me"] == {
        "enabled": True,
        "grace_min": 15,
        "escalate_min": 15,
    }
    assert client.post("/cards/safety/context").status_code == 501


def test_message_reaction_requires_audience_grant_and_current_version():
    owner = TestClient(app)
    viewer = TestClient(app)
    owner_data = owner.post("/auth/register", json={
        "name": "Message Owner",
        "email": "reaction-owner@example.com",
        "password": "password123",
    }).json()
    viewer_data = viewer.post("/auth/register", json={
        "name": "Message Viewer",
        "email": "reaction-viewer@example.com",
        "password": "password123",
    }).json()
    connection = owner.post("/connections/request", json={"user_code": viewer_data["user_code"]})
    connection_id = connection.json()["id"]
    viewer.post(f"/connections/{connection_id}/accept")
    grant = owner.put(f"/grants/{viewer_data['id']}", json={
        "cards": {"message": "details"},
    })
    assert grant.status_code == 200

    message = owner.post("/cards/message", json={
        "template_key": "cant_talk",
        "audience": [viewer_data["id"]],
    })
    assert message.status_code == 201
    message_id = message.json()["id"]

    broadcast = owner.post("/cards/message", json={"text": "Running late, call after 6"})
    assert broadcast.status_code == 201
    assert broadcast.json()["record"]["audience"] == [viewer_data["id"]]
    viewer_messages = viewer.get(f"/state/{owner_data['id']}").json()["messages"]
    assert any(item.get("text") == "Running late, call after 6" for item in viewer_messages)

    reaction = viewer.post(f"/cards/messages/{message_id}/reactions", json={
        "reaction": "OK",
        "version": 1,
    })
    assert reaction.status_code == 200
    assert reaction.json()["version"] == 2

    stale = viewer.post(f"/cards/messages/{message_id}/reactions", json={
        "reaction": "Call me later",
        "version": 1,
    })
    assert stale.status_code == 409
