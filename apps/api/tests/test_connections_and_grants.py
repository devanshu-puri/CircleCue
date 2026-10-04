import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_connection_and_grants_full_flow(mock_db):
    client_a = TestClient(app)
    client_b = TestClient(app)

    # 1. Register User A
    resp_a = client_a.post("/auth/register", json={
        "name": "Alpha Smith",
        "email": "alpha@example.com",
        "password": "password123"
    })
    assert resp_a.status_code == 201
    user_a_data = resp_a.json()
    mock_db.users.docs[user_a_data["id"]]["tz"] = "Asia/Kolkata"
    mock_db.templates.docs["private-class"] = {
        "_id": "private-class",
        "owner": user_a_data["id"],
        "title": "Physics Lecture",
        "activity_type": "CLASS",
        "days": [5],
        "start_local": "09:00",
        "end_local": "10:00",
        "visibility": {"mode": "private_label", "label_override": "Personal"},
        "availability": {"calls": "no"},
    }

    # 2. Register User B
    resp_b = client_b.post("/auth/register", json={
        "name": "Beta Johnson",
        "email": "beta@example.com",
        "password": "password123"
    })
    assert resp_b.status_code == 201
    user_b_data = resp_b.json()
    code_b = user_b_data["user_code"]

    # 3. User A requests connection to User B
    req_resp = client_a.post("/connections/request", json={"user_code": code_b})
    assert req_resp.status_code == 201
    conn_id = req_resp.json()["id"]

    # 4. User B accepts connection
    accept_resp = client_b.post(f"/connections/{conn_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "active"

    state_without_grant = client_b.get(f"/state/{user_a_data['id']}")
    assert state_without_grant.status_code == 200
    assert state_without_grant.json()["activity"] is None

    # 5. User A tries to set grant for B -> Success
    grant_resp = client_a.put(f"/grants/{user_b_data['id']}", json={
        "relationship_preset": "friend",
        "cards": {"travel": "status", "live": "details", "schedule": "status"},
        "notify": {"free_now": True, "activity": True}
    })
    assert grant_resp.status_code == 200
    assert grant_resp.json()["cards"]["travel"] == "status"

    live_activity = client_a.post("/cards/live", json={
        "type": "STUDY",
        "title": "Revision in progress",
        "availability": {"calls": "no"},
    })
    assert live_activity.status_code == 201

    projected_state = client_b.get(f"/state/{user_a_data['id']}")
    assert projected_state.status_code == 200
    assert projected_state.json()["owner"] == user_a_data["id"]
    assert projected_state.json()["activity"]["label"] == "Revision in progress"
    alerts = client_b.get("/notifications")
    assert alerts.status_code == 200
    assert len(alerts.json()) == 1
    assert alerts.json()[0]["payload_redacted"]["text"] == "Now: Revision in progress"

    updated_activity = client_a.patch(f"/cards/live/{live_activity.json()['id']}", json={
        "version": live_activity.json()["record"]["version"],
        "title": "Math revision in progress",
    })
    assert updated_activity.status_code == 200
    refreshed_state = client_b.get(f"/state/{user_a_data['id']}")
    assert refreshed_state.json()["activity"]["label"] == "Math revision in progress"
    updated_alerts = client_b.get("/notifications")
    assert len(updated_alerts.json()) == 2
    updated_alert = next(
        item for item in updated_alerts.json()
        if item["kind"] == "ACTIVITY_EXTENDED"
    )
    assert updated_alert["payload_redacted"]["text"] == "Activity updated: Math revision in progress"
    read_alert = client_b.post(f"/notifications/{updated_alert['_id']}/read")
    assert read_alert.status_code == 200

    shared_timeline = client_b.get(
        f"/timeline/{user_a_data['id']}", params={"date": "2026-10-03"}
    )
    assert shared_timeline.status_code == 200
    assert shared_timeline.json()["segments"][0]["label"] == "Personal"

    owner_timeline = client_a.get("/timeline", params={"date": "2026-10-03"})
    assert owner_timeline.status_code == 200
    assert owner_timeline.json()["segments"][0]["label"] == "Physics Lecture"

    # 6. Check outgoing & incoming grants
    outgoing_resp = client_a.get("/grants/outgoing")
    assert outgoing_resp.status_code == 200
    assert len(outgoing_resp.json()) == 1
    assert client_a.get("/grants/outgoing").json()[0]["notify"]["activity"] is True

    incoming_resp = client_b.get("/grants/incoming")
    assert incoming_resp.status_code == 200
    assert len(incoming_resp.json()) == 1
    assert incoming_resp.json()[0]["cards"]["live"] == "details"

    # 7. Revoke Grant
    revoke_resp = client_a.delete(f"/grants/{user_b_data['id']}")
    assert revoke_resp.status_code == 200

    # Incoming list should be empty after revocation
    incoming_after = client_b.get("/grants/incoming")
    assert incoming_after.status_code == 200
    assert len(incoming_after.json()) == 0
    revoked_timeline = client_b.get(f"/timeline/{user_a_data['id']}")
    assert revoked_timeline.status_code == 403

    # 8. User B blocks User A
    block_resp = client_b.post(f"/connections/{conn_id}/block")
    assert block_resp.status_code == 200
    assert block_resp.json()["message"] == "User blocked and all mutual access revoked"
