import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.sanitize import sanitize_user_text
from app.core.ratelimit import RateLimiter
from app.core.errors import CircleCueError

def test_security_headers_present_on_all_responses():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

def test_sanitize_user_text_strips_html_and_limits_length():
    raw = "<script>alert('hack')</script><b>Hello</b>   world! &amp; friends"
    clean = sanitize_user_text(raw, max_len=20)
    assert "<script>" not in clean
    assert "<b>" not in clean
    assert len(clean) <= 20
    assert "Hello world!" in clean or "alert('hack')Hello" in clean

def test_rate_limiter_blocks_excessive_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    user_key = "user-123"
    
    # 3 allowed
    limiter.check(user_key)
    limiter.check(user_key)
    limiter.check(user_key)
    
    # 4th raises 429
    with pytest.raises(CircleCueError) as exc_info:
        limiter.check(user_key)
    assert exc_info.value.status_code == 429

def test_sentry_test_error_endpoint():
    client = TestClient(app)
    # /debug/sentry should raise RuntimeError in dev
    with pytest.raises(RuntimeError, match="Test Sentry Error"):
        client.get("/debug/sentry")
