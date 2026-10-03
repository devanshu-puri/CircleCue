from datetime import timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.clock import SystemClock, DemoClock
from app.main import app

def test_system_clock():
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc

def test_demo_clock():
    clock = DemoClock()
    base_time = clock.now()
    
    clock.advance(timedelta(minutes=30))
    advanced_time = clock.now()
    diff = (advanced_time - base_time).total_seconds()
    assert diff >= 1800  # at least 30 minutes

    clock.reset()
    reset_time = clock.now()
    reset_diff = (reset_time - base_time).total_seconds()
    assert reset_diff < 5

def test_healthz_endpoint():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "circlecue-api"

def test_readyz_endpoint():
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "clock_now" in data

def test_debug_sentry_endpoint():
    client = TestClient(app)
    with pytest.raises(RuntimeError) as exc_info:
        client.get("/debug/sentry")
    assert "Test Sentry Error" in str(exc_info.value)
