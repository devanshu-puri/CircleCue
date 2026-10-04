import os
from datetime import datetime, timezone
import pytest

from app.ai.service import AIService

pytestmark = pytest.mark.skipif(
    os.getenv("AI_PROVIDER") != "openai_compat",
    reason="Live model test requires AI_PROVIDER=openai_compat",
)


@pytest.mark.asyncio
async def test_live_parse_simple():
    now = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    service = AIService()
    outcome = await service.parse("class at 9am to 11am", "schedule", now, "Asia/Kolkata", [])
    assert outcome.schema_valid
    assert outcome.result.intent in ("activity", "schedule")
    assert outcome.provider != "rules"
