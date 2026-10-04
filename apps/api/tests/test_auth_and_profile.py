import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import generate_user_code, hash_password, verify_password

def test_user_code_format():
    code1 = generate_user_code("Rahul Sharma")
    assert code1.startswith("RAHUL-")
    assert len(code1) == 10 # RAHUL- (6) + 4 = 10

    code2 = generate_user_code("A B")
    assert code2.startswith("A-")

def test_password_hashing():
    pw = "SecretPass123!"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPass", hashed) is False

def test_auth_and_profile_flow():
    client = TestClient(app)

    # 1. Register
    reg_resp = client.post("/auth/register", json={
        "name": "Devanshu Kumar",
        "email": "devanshu@example.com",
        "password": "mysecurepassword",
        "tz": "Asia/Kolkata"
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["name"] == "Devanshu Kumar"
    assert "user_code" in reg_data
    assert reg_data["user_code"].startswith("DEVANS-")

    # Check cookie set
    assert "access_token" in client.cookies

    # 2. GET /me
    me_resp = client.get("/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "devanshu@example.com"
    assert me_data["routine_prefs"]["wake"] == "07:00"

    # 3. Code Lookup
    user_code = reg_data["user_code"]
    lookup_resp = client.get(f"/users/code-lookup?code={user_code}")
    assert lookup_resp.status_code == 200
    lookup_data = lookup_resp.json()
    assert lookup_data["user_code"] == user_code
    assert lookup_data["name"] == "Devanshu" # Only first name returned

    # 4. Code Rotation
    rotate_resp = client.post("/me/code/rotate")
    assert rotate_resp.status_code == 200
    new_code = rotate_resp.json()["user_code"]
    assert new_code != user_code

    # 5. Sharing Pause
    pause_resp = client.post("/me/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["sharing_paused"]["active"] is True

    unpause_resp = client.delete("/me/pause")
    assert unpause_resp.status_code == 200
    assert unpause_resp.json()["sharing_paused"]["active"] is False

    # 6. Data Export
    export_resp = client.get("/me/export")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "user" in export_data
    assert "pw_hash" not in export_data["user"]

    # 7. Logout
    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 200

    # 8. Login
    login_resp = client.post("/auth/login", json={
        "email": "devanshu@example.com",
        "password": "mysecurepassword"
    })
    assert login_resp.status_code == 200
    assert "access_token" in client.cookies
