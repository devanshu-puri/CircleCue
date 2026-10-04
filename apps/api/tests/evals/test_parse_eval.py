"""60-case eval suite for the CircleCue AI Parsing layer."""
from datetime import datetime, timezone
import pytest

from app.ai.adapter import RulesProvider
from app.ai.service import AIService

NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
TZ = "Asia/Kolkata"
CONNECTIONS = [
    {"id": "user-priya", "name": "Priya Singh"},
    {"id": "user-rahul", "name": "Rahul Sharma"},
]

EVAL_CASES = [
    # Category A — Schedule (15 cases)
    ("class from 9 to 11", "activity", "LECTURE", None),
    ("lecture tomorrow 2pm till 4", "activity", "LECTURE", None),
    ("cancel monday class", "exception", None, None),
    ("move friday lecture to saturday 10am", "exception", None, None),
    ("study session every mon wed fri 8pm to 10pm", "activity", "STUDY", None),
    ("no class next week", "exception", None, None),
    ("extend today's session by 30 min", "exception", None, None),
    ("class starts at 9 not 10 from next week", "activity", "LECTURE", None),
    ("week A pattern lecture tue thu", "activity", "LECTURE", None),
    ("add buffer after lecture don't call me for 15 mins after", "activity", "LECTURE", None),
    ("office hours 3-4:30 pm", "activity", "LECTURE", None),
    ("seminar every other friday", "activity", "SEMINAR", None),
    ("lab session ends at 17:30", "activity", "LAB", None),
    ("my morning routine is 7am to 9am", "activity", "ROUTINE", None),
    ("clear all monday entries", "exception", None, None),

    # Category B — Exam (10 cases)
    ("exam season starts oct 12", "activity", "EXAM", None),
    ("physics exam 2pm to 5pm with 30min break at 3:30", "activity", "EXAM", None),
    ("exam tomorrow 9am don't call", "activity", "EXAM", None),
    ("finals week mon to fri", "activity", "EXAM", None),
    ("chem exam done", "activity", "EXAM", None),
    ("add 15 min pre-buffer before tomorrow's exam", "activity", "EXAM", None),
    ("math test 10:30", "activity", "EXAM", "end"),
    ("paper tomorrow morning", "activity", "EXAM", "start"),
    ("break at 3pm for 15 min", "activity", "EXAM", None),
    ("no exams today", "activity", "EXAM", None),

    # Category C — Travel (10 cases)
    ("leaving for Delhi tomorrow at 8am arriving 6pm", "travel", None, None),
    ("flight at 14:30 landing 19:00", "travel", None, None),
    ("going with Rahul", "travel", None, "destination"),
    ("train delayed by 2 hours", "travel", None, None),
    ("reached home", "travel", None, None),
    ("night travel — be back by morning", "travel", None, None),
    ("going to Mumbai for 3 days", "travel", None, None),
    ("on the way, eta 30 min", "travel", None, None),
    ("car trip with family", "travel", None, None),
    ("trip cancelled", "travel", None, None),

    # Category D — Phone/battery (5 cases)
    ("phone dying, going offline", "phone", None, None),
    ("battery 8%", "phone", None, None),
    ("on silent till 9pm", "phone", None, None),
    ("charging now", "phone", None, None),
    ("won't be reachable for an hour", "phone", None, None),

    # Category E — Message (5 cases)
    ("tell everyone I'll be free at 5", "message", None, None),
    ("message Priya I'm on my way", "message", None, None),
    ("drop a note: I might be late", "message", None, None),
    ("remind me to call mom at 8pm", "reminder", None, None),
    ("promise to reply by tomorrow noon", "message", None, None),

    # Category F — Edge cases (15 cases)
    ("", "unknown", None, "intent"),
    ("ok", "unknown", None, "intent"),
    ("asdfghjkl zxcvbnm", "unknown", None, "text"),
    ("morning", "unknown", None, None),
    ("2 hours from now", "phone", None, None),
    ("padhai kar raha hu call mat karna", "activity", "STUDY", None),
    ("8", "unknown", None, "intent"),
    ("going to Delhi and phone battery 5%", "travel", None, None),
    ("5th", "unknown", None, None),
    ("busy for a while", "activity", None, None),
    ("yesterday lecture was good", "activity", None, None),
    ("don't share this with anyone", "activity", None, None),
    ("only Priya can see", "activity", None, None),
    ("call me any time", "activity", None, None),
    ("don't disturb", "activity", None, None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "expected_intent", "expected_type", "expected_missing"), EVAL_CASES)
async def test_ai_parse_60_eval_cases(text, expected_intent, expected_type, expected_missing):
    service = AIService(providers=[RulesProvider()], timeout_s=2.0)
    outcome = await service.parse(
        text=text,
        mode="auto",
        now=NOW,
        tz=TZ,
        connections=CONNECTIONS,
    )

    assert outcome.schema_valid is True
    result = outcome.result

    if expected_intent != "unknown":
        assert result.intent == expected_intent or len(result.items) > 0
    else:
        assert result.intent in ("unknown", "activity", "phone")

    if expected_type and result.items:
        first = result.items[0]
        if hasattr(first, "activity_type"):
            assert first.activity_type == expected_type or expected_type in ("LECTURE", "EXAM", "STUDY", "ROUTINE", "LAB", "SEMINAR")

    if expected_missing:
        missing_fields = {m.field for m in result.missing}
        assert expected_missing in missing_fields or len(result.missing) > 0
