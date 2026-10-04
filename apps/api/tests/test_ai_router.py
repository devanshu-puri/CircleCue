from fastapi.testclient import TestClient

from app.main import app


def test_ai_parse_returns_drafts_without_persisting_activity(mock_db):
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "AI Owner",
        "email": "ai-owner@example.com",
        "password": "password123",
        "tz": "Asia/Kolkata",
    })
    assert register.status_code == 201

    response = client.post("/ai/parse", json={
        "text": "studying till 8, no calls",
        "mode": "activity",
    })

    assert response.status_code == 200
    assert response.json()["items"][0]["kind"] == "activity"
    assert response.json()["items"][0]["availability"]["calls"] == "no"
    assert response.json()["items"][0]["resolved_end_at"]
    assert mock_db.activities.docs == {}
    invocation = next(iter(mock_db.ai_invocations.docs.values()))
    assert "raw_text" not in invocation


def test_ai_parse_stores_raw_text_only_after_owner_opt_in(mock_db):
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "AI Owner",
        "email": "ai-owner-raw@example.com",
        "password": "password123",
    })
    owner_id = register.json()["id"]
    mock_db.users.docs[owner_id]["ai_prefs"] = {"store_raw": True}

    response = client.post("/ai/parse", json={"text": "phone battery 5%"})

    assert response.status_code == 200
    invocation = next(iter(mock_db.ai_invocations.docs.values()))
    assert invocation["raw_text"] == "phone battery 5%"


def test_ai_confirm_persists_owner_confirmed_activity(mock_db):
    client = TestClient(app)
    other_client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Confirm Owner",
        "email": "confirm-owner@example.com",
        "password": "password123",
    })
    owner_id = register.json()["id"]
    parsed = client.post("/ai/parse", json={"text": "studying till 8, no calls"})
    assert parsed.status_code == 200

    other_client.post("/auth/register", json={
        "name": "Other User",
        "email": "confirm-other@example.com",
        "password": "password123",
    })
    forbidden = other_client.post("/ai/confirm", json={
        "draft_id": parsed.json()["draft_id"],
        "items": parsed.json()["items"],
    })
    assert forbidden.status_code == 404

    unsupported = client.post("/ai/confirm", json={
        "draft_id": parsed.json()["draft_id"],
        "items": [{"kind": "reminder", "title": "Call Mom"}],
    })
    assert unsupported.status_code == 501
    assert mock_db.ai_invocations.docs[parsed.json()["draft_id"]]["confirmed"] is False

    confirmed = client.post("/ai/confirm", json={
        "draft_id": parsed.json()["draft_id"],
        "items": parsed.json()["items"],
    })

    assert confirmed.status_code == 201
    assert confirmed.json()["records"][0]["record"]["owner"] == owner_id
    assert confirmed.json()["records"][0]["record"]["provenance"]["source"] == "ai_parsed_user_confirmed"
    invocation = mock_db.ai_invocations.docs[parsed.json()["draft_id"]]
    assert invocation["confirmed"] is True
    duplicate = client.post("/ai/confirm", json={
        "draft_id": parsed.json()["draft_id"],
        "items": parsed.json()["items"],
    })
    assert duplicate.status_code == 409


def test_ai_confirm_persists_time_scenario(mock_db):
    client = TestClient(app)
    register = client.post("/auth/register", json={
        "name": "Scenario AI Owner",
        "email": "scenario-ai-owner@example.com",
        "password": "password123",
    })
    assert register.status_code == 201
    parsed = client.post("/ai/parse", json={
        "text": "Every Friday 7-10 I play cricket, don't notify people I'm available",
        "mode": "scenario",
    })
    assert parsed.status_code == 200

    confirmed = client.post("/ai/confirm", json={
        "draft_id": parsed.json()["draft_id"],
        "items": parsed.json()["items"],
    })

    assert confirmed.status_code == 201
    scenario = confirmed.json()["records"][0]
    assert scenario["trigger"]["kind"] == "time"
    assert scenario["effects"][0]["kind"] == "set_activity"
    assert scenario["effects"][1]["kind"] == "suppress_notifications"