"""
Seed demo data for CircleCue.

Usage:
    python scripts/seed_demo.py [--base-url http://localhost:8000]

Creates:
    - User A: Arjun Kumar (arjun@demo.circlecue.app / demo-password-arjun)
    - User B: Priya Singh (priya@demo.circlecue.app / demo-password-priya)
    - Mutual connection + grants
    - Arjun's schedule templates (lectures, study sessions)
    - Arjun's active exam set (Oct 5 engineering paper)
    - Arjun's active travel activity (Delhi trip, check-on-me enabled)
    - Arjun's connection plan for Priya
    - Priya's routine template
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Seed CircleCue demo data")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SEED_API_URL", "http://localhost:8000"),
        help="Base URL for the CircleCue API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="If users already exist, skip with a warning instead of failing",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"\n CircleCue Demo Seed  Target: {base}\n")

    client = httpx.Client(base_url=base, timeout=15)

    #  Register Arjun 
    print("1/10  Registering Arjun Kumar...")
    try:
        arjun_reg = client.post("/auth/register", json={
            "name": "Arjun Kumar",
            "email": "arjun@demo.circlecue.app",
            "password": "demo-password-arjun",
            "tz": "Asia/Kolkata",
        })
        arjun_reg.raise_for_status()
        arjun = arjun_reg.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (409, 400):
            print("      Arjun already exists  logging in instead")
            arjun_login = client.post("/auth/login", json={
                "email": "arjun@demo.circlecue.app",
                "password": "demo-password-arjun",
            })
            arjun_login.raise_for_status()
            arjun = arjun_login.json()
            arjun_reg = arjun_login
        else:
            raise

    arjun_id = arjun["id"]
    arjun_code = arjun.get("user_code", "ARJUN-????")
    arjun_cookies = dict(arjun_reg.cookies if not args.reset else {})
    if not arjun_cookies:
        login_r = client.post("/auth/login", json={
            "email": "arjun@demo.circlecue.app",
            "password": "demo-password-arjun",
        })
        arjun_cookies = dict(login_r.cookies)

    ac = client  # will set cookies per request

    def arjun_post(path: str, body: Any) -> Dict:
        r = client.post(path, json=body, cookies=arjun_cookies)
        r.raise_for_status()
        return r.json()

    def arjun_put(path: str, body: Any) -> Dict:
        r = client.put(path, json=body, cookies=arjun_cookies)
        r.raise_for_status()
        return r.json()

    print(f"      Arjun: id={arjun_id}, code={arjun_code}")

    #  Register Priya 
    print("2/10  Registering Priya Singh...")
    try:
        priya_reg = client.post("/auth/register", json={
            "name": "Priya Singh",
            "email": "priya@demo.circlecue.app",
            "password": "demo-password-priya",
            "tz": "Asia/Kolkata",
        })
        priya_reg.raise_for_status()
        priya = priya_reg.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (409, 400):
            print("      Priya already exists  logging in instead")
            priya_login = client.post("/auth/login", json={
                "email": "priya@demo.circlecue.app",
                "password": "demo-password-priya",
            })
            priya_login.raise_for_status()
            priya = priya_login.json()
            priya_reg = priya_login
        else:
            raise

    priya_id = priya["id"]
    priya_code = priya.get("user_code", "PRIYA-????")
    priya_cookies = dict(priya_reg.cookies)
    if not priya_cookies:
        priya_login_r = client.post("/auth/login", json={
            "email": "priya@demo.circlecue.app",
            "password": "demo-password-priya",
        })
        priya_cookies = dict(priya_login_r.cookies)

    def priya_post(path: str, body: Any) -> Dict:
        r = client.post(path, json=body, cookies=priya_cookies)
        r.raise_for_status()
        return r.json()

    def priya_put(path: str, body: Any) -> Dict:
        r = client.put(path, json=body, cookies=priya_cookies)
        r.raise_for_status()
        return r.json()

    print(f"      Priya: id={priya_id}, code={priya_code}")

    #  Connect Arjun  Priya 
    print("3/10  Establishing mutual connection...")
    try:
        conn_req = arjun_post("/connections/request", {"user_code": priya_code})
        conn_id = conn_req.get("id") or conn_req.get("_id")
        # Priya accepts
        priya_post(f"/connections/{conn_id}/accept", {})
        print(f"      Connection active: {conn_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (409, 400, 422):
            print("      Already connected  continuing")
            # look up existing connection id
            conn_list = client.get("/connections", cookies=arjun_cookies)
            conns = conn_list.json() if conn_list.status_code == 200 else []
            conn_id = next(
                (c.get("_id") or c.get("id") for c in conns
                 if c.get("status") == "active"),
                None,
            )
            print(f"      Using existing connection: {conn_id}")
        else:
            raise

    #  Arjun grants Priya detailed access 
    print("4/10  Setting up Arjun  Priya grants...")
    arjun_put(f"/grants/{priya_id}", {
        "relationship_preset": "friend",
        "cards": {
            "schedule": "details",
            "exam": "status",
            "live": "status",
            "travel": "status",
            "phone": "status",
            "safety": "details",
            "message": "status",
        },
        "notify": {
            "travel": True,
            "exam": True,
            "safety": True,
            "free_now": True,
            "battery": True,
        },
        "important": True,
        "reach_through": False,
    })
    print("      Grants set")

    # Priya grants Arjun schedule + live status
    priya_put(f"/grants/{arjun_id}", {
        "relationship_preset": "friend",
        "cards": {
            "schedule": "status",
            "live": "status",
        },
        "notify": {"free_now": True},
    })
    print("      Priya  Arjun grants set")

    #  Arjun's schedule templates 
    print("5/10  Creating Arjun's schedule templates...")
    # Mon/Wed/Fri Engineering Lecture (CLASS  valid for schedule card)
    arjun_post("/cards/schedule", {
        "title": "Engineering Lecture",
        "activity_type": "CLASS",
        "kind": "SCHEDULE_SLOT",
        "days": [0, 2, 4],
        "start_local": "09:00",
        "end_local": "11:00",
        "availability": {"calls": "no", "messages": "later"},
    })
    # Mon/Wed Lab session (LAB  valid for schedule card)
    arjun_post("/cards/schedule", {
        "title": "Lab Session",
        "activity_type": "LAB",
        "kind": "SCHEDULE_SLOT",
        "days": [0, 2],
        "start_local": "20:00",
        "end_local": "22:00",
        "availability": {"calls": "prefer_not", "messages": "ok"},
    })
    print("      Schedule templates created")

    #  Arjun's exam set (Oct 5) 
    print("6/10  Creating Arjun's exam set for Oct 5...")
    arjun_post("/cards/exam/season", {
        "date": "2026-10-05",
        "items": [
            {
                "type": "exam",
                "subject": "Engineering Paper",
                "start_local": "09:00",
                "end_local": "12:00",
                "calls_ok": False,
            }
        ],
        "pre_buffer_min": 30,
        "post_buffer_min": 15,
        "keep_schedule": False,
    })
    print("      Exam set created")

    #  Arjun's active travel activity 
    print("7/10  Creating Arjun's active travel to Delhi...")
    now_utc = datetime.now(timezone.utc)
    eta_utc = (now_utc + timedelta(hours=6, minutes=30)).replace(microsecond=0)
    travel = arjun_post("/cards/travel", {
        "title": "Travelling to Delhi",
        "type": "TRAVEL",
        "activity_type": "TRAVEL",
        "start_at": now_utc.isoformat(),
        "expected_end_at": eta_utc.isoformat(),
        "availability": {"calls": "prefer_not", "messages": "ok"},
        "metadata": {
            "kind": "travel",
            "destination": "Delhi",
            "destination_kind": "city",
            "depart": now_utc.isoformat(),
            "eta": eta_utc.isoformat(),
            "mode": "train",
            "companions": [],
        },
        "check_on_me": {
            "enabled": True,
            "grace_min": 15,
            "escalate_min": 15,
        },
        "provenance": {"source": "user_shared"},
    })
    travel_id = travel.get("id") or travel.get("_id") or travel.get("record", {}).get("_id")
    print(f"      Travel activity: id={travel_id}, ETA={eta_utc.isoformat()}")

    #  Arjun's connection plan for Priya 
    print("8/10  Adding connection reminder plan for Priya...")
    arjun_post("/reminders/plans", {
        "target": priya_id,
        "importance": "high",
        "rule": "weekly",
        "cooldown_min": 1440,
    })
    print("      Connection plan created")

    #  Priya's morning routine 
    print("9/10  Creating Priya's routine...")
    priya_post("/cards/schedule", {
        "title": "Morning Routine",
        "activity_type": "FREE_PERIOD",
        "kind": "SCHEDULE_SLOT",
        "days": [1, 3],  # Tue, Thu
        "start_local": "08:00",
        "end_local": "09:00",
        "availability": {"calls": "prefer_not", "messages": "ok"},
    })
    print("      Priya's routine created")

    #  Phone state for Arjun (travelling, low battery) 
    print("10/10 Setting Arjun's phone state (travelling, low battery)...")
    arjun_post("/cards/phone", {
        "mode": "normal",
        "calls": "prefer_not",
        "messages": "ok",
        "battery_pct": 28,
        "may_go_offline": False,
    })
    print("      Phone state set")

    #  Summary 
    print("\n" + "=" * 60)
    print(" SEED COMPLETE")
    print("=" * 60)
    print(f"\n  Arjun Kumar")
    print(f"    Email   : arjun@demo.circlecue.app")
    print(f"    Password: demo-password-arjun")
    print(f"    Code    : {arjun_code}")
    print(f"    ID      : {arjun_id}")
    print(f"\n  Priya Singh")
    print(f"    Email   : priya@demo.circlecue.app")
    print(f"    Password: demo-password-priya")
    print(f"    Code    : {priya_code}")
    print(f"    ID      : {priya_id}")
    print("\n  Seeded data:")
    print("    - Mutual connection (active)")
    print("    - Arjun  Priya: schedule/exam/travel/phone/safety grants")
    print("    - Arjun: 2 schedule templates (lecture MWF + study MW)")
    print("    - Arjun: Exam set Oct 5 (Engineering Paper 09:0012:00)")
    print("    - Arjun: Active travel to Delhi, check-on-me enabled")
    print("    - Arjun: High-importance connection plan for Priya")
    print("    - Priya: Morning routine (Tue/Thu 08:0009:00)")
    print("    - Arjun: Phone state (low battery, prefer_not calls)")
    print("\n  API: " + base)
    print("  Docs: " + base + "/docs  (development only)")
    print()


if __name__ == "__main__":
    main()
