import pytest
from pydantic import ValidationError as PydanticValidationError
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.ai.schemas import ParseResult, TimeSpec, TravelDraft, PhoneDraft
from app.ai.timeparse import resolve_time_spec
from app.ai.adapter import OpenAICompatProvider, OllamaProvider, RulesProvider
from app.ai.service import AIService


def test_parse_result_uses_discriminated_draft_union():
    result = ParseResult.model_validate({
        "intent": "travel",
        "language": "en",
        "confidence": 0.8,
        "items": [
            {
                "kind": "travel",
                "destination": "Home",
                "companion": "Rahul",
                "eta": {"relative_min": 40},
            },
            {
                "kind": "phone",
                "battery_pct": 5,
                "may_go_offline": True,
            },
        ],
    })

    assert isinstance(result.items[0], TravelDraft)
    assert isinstance(result.items[1], PhoneDraft)


@pytest.mark.parametrize(
    "time_value",
    [
        {"hh_mm": "8", "ampm_assumed": True},
        {"hh_mm": "16:30"},
        {"relative_min": 40},
        {"hh_mm": "08:00", "date_ref": "tomorrow"},
    ],
)
def test_time_spec_accepts_absolute_and_relative_values(time_value):
    assert TimeSpec.model_validate(time_value)


def test_time_spec_rejects_missing_or_ambiguous_time():
    with pytest.raises(PydanticValidationError):
        TimeSpec.model_validate({"date_ref": "tomorrow"})
    with pytest.raises(PydanticValidationError):
        TimeSpec.model_validate({"hh_mm": "8", "relative_min": 40})


def test_ambiguous_afternoon_time_resolves_to_next_pm_occurrence():
    now = datetime(2026, 10, 3, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    resolved = resolve_time_spec(
        TimeSpec(hh_mm="8", ampm_assumed=True), now, "Asia/Kolkata"
    )

    assert resolved == datetime(2026, 10, 3, 20, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


def test_ambiguous_pm_time_after_its_boundary_rolls_to_next_day_pm():
    now = datetime(2026, 10, 3, 17, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    resolved = resolve_time_spec(
        TimeSpec(hh_mm="4", ampm_assumed=True), now, "Asia/Kolkata"
    )

    assert resolved == datetime(2026, 10, 4, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


def test_relative_and_tomorrow_times_use_injected_clock_and_owner_timezone():
    now = datetime(2026, 10, 3, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    relative = resolve_time_spec(TimeSpec(relative_min=40), now, "Asia/Kolkata")
    tomorrow = resolve_time_spec(
        TimeSpec(hh_mm="9", date_ref="tomorrow", ampm_assumed=True),
        now,
        "Asia/Kolkata",
    )

    assert relative == (now + timedelta(minutes=40)).astimezone(timezone.utc)
    assert tomorrow == datetime(2026, 10, 4, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_kinds"),
    [
        ("Studying till 8, no calls", ["activity"]),
        ("Going home with Rahul, reach in 40 min, battery 5%", ["travel", "phone"]),
        ("Class got cancelled today", ["exception"]),
        ("Every Friday 7-10 I play cricket, don't notify people I'm available", ["scenario"]),
    ],
)
async def test_rules_provider_parses_demo_utterances(text, expected_kinds):
    import json

    from datetime import datetime, timezone

    provider = RulesProvider()
    output = await provider.generate_structured(
        system="parse",
        user=json.dumps({
            "text": text,
            "now": datetime(2026, 10, 3, 10, tzinfo=timezone.utc).isoformat(),
            "tz": "Asia/Kolkata",
            "connection_names": ["Rahul"],
        }),
        json_schema=ParseResult.model_json_schema(),
        timeout=1.0,
    )
    result = ParseResult.model_validate(output)

    assert [item.kind for item in result.items] == expected_kinds


@pytest.mark.asyncio
async def test_rules_provider_builds_time_scenario_without_persisting_it():
    import json

    provider = RulesProvider()
    output = await provider.generate_structured(
        system="parse",
        user=json.dumps({"text": "Every Friday 7-10 I play cricket, don't notify people I'm available"}),
        json_schema=ParseResult.model_json_schema(),
        timeout=1.0,
    )
    result = ParseResult.model_validate(output)

    assert result.intent == "scenario"
    assert result.items[0].trigger["weekday"] == "friday"
    assert result.items[0].effects[-1]["notification"] == "FREE_NOW"


class SequenceProvider:
    name = "fake"
    model = "fake-v1"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def generate_structured(self, system, user, json_schema, timeout):
        self.calls += 1
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


@pytest.mark.asyncio
async def test_service_resolves_eta_and_matches_owner_connection():
    now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    service = AIService(providers=[RulesProvider()], timeout_s=1.0)

    outcome = await service.parse(
        "Going home with Rahul, reach in 40 min, battery 5%",
        "activity",
        now,
        "Asia/Kolkata",
        connections=[{"id": "connection-user-1", "name": "Rahul Sharma"}],
    )

    travel = outcome.result.items[0]
    assert travel.kind == "travel"
    assert travel.companion_id == "connection-user-1"
    assert travel.resolved_eta_at == (now + timedelta(minutes=40)).isoformat()
    assert outcome.result.items[1].kind == "phone"


@pytest.mark.asyncio
async def test_service_asks_when_companion_name_is_ambiguous():
    now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    service = AIService(providers=[RulesProvider()], timeout_s=1.0)

    outcome = await service.parse(
        "Going home with Rahul, reach in 40 min",
        "travel",
        now,
        "Asia/Kolkata",
        connections=[
            {"id": "u1", "name": "Rahul Sharma"},
            {"id": "u2", "name": "Rahul Kumar"},
        ],
    )

    assert outcome.result.items[0].companion_id is None
    assert any(item.field == "companion" for item in outcome.result.missing)


@pytest.mark.asyncio
async def test_service_maps_message_audience_to_connected_user_ids():
    now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    provider = SequenceProvider([{
        "intent": "message",
        "language": "en",
        "confidence": 0.9,
        "items": [{"kind": "message", "text": "Call me later", "audience": ["Rahul"]}],
    }])
    service = AIService(providers=[provider], timeout_s=1.0)

    outcome = await service.parse(
        "Tell Rahul to call me later",
        "message",
        now,
        "UTC",
        connections=[{"id": "user-1", "name": "Rahul Sharma"}],
    )

    assert outcome.result.items[0].audience == ["user-1"]


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeHttpClient:
    def __init__(self, response_body):
        self.response_body = response_body
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return FakeResponse(self.response_body)


@pytest.mark.asyncio
async def test_openai_compatible_provider_uses_json_schema_response_format(monkeypatch):
    import app.ai.adapter as adapter

    body = {"choices": [{"message": {"content": '{"intent":"unknown"}'}}]}
    client = FakeHttpClient(body)
    monkeypatch.setattr(adapter.httpx, "AsyncClient", lambda timeout: client)
    provider = OpenAICompatProvider("http://model/v1", "gemma", "token")

    output = await provider.generate_structured("system", "user", {"type": "object"}, 1.0)

    assert output == {"intent": "unknown"}
    assert client.request["url"] == "http://model/v1/chat/completions"
    assert client.request["json"]["response_format"]["json_schema"]["schema"] == {"type": "object"}


@pytest.mark.asyncio
async def test_ollama_provider_uses_native_format_schema(monkeypatch):
    import app.ai.adapter as adapter

    client = FakeHttpClient({"message": {"content": '{"intent":"unknown"}'}})
    monkeypatch.setattr(adapter.httpx, "AsyncClient", lambda timeout: client)
    provider = OllamaProvider("http://localhost:11434/v1", "gemma")

    output = await provider.generate_structured("system", "user", {"type": "object"}, 1.0)

    assert output == {"intent": "unknown"}
    assert client.request["url"] == "http://localhost:11434/api/chat"
    assert client.request["json"]["format"] == {"type": "object"}


@pytest.mark.asyncio
async def test_significance_judge_is_restricted_to_custom_events():
    service = AIService(providers=[RulesProvider()], timeout_s=1.0)

    decision = await service.significance_judge("CUSTOM", "Please call, this is urgent")

    assert decision.notify is True
    with pytest.raises(ValueError, match="restricted"):
        await service.significance_judge("ACTIVITY_STARTED", "Please call")


@pytest.mark.asyncio
async def test_service_repairs_invalid_primary_then_falls_back_to_rules():
    now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    broken = SequenceProvider([{"confidence": 2}, RuntimeError("provider down")])
    service = AIService(providers=[broken, RulesProvider()], timeout_s=1.0)

    outcome = await service.parse("Studying till 8, no calls", "activity", now, "UTC")

    assert broken.calls == 2
    assert outcome.provider == "rules"
    assert outcome.result.items[0].kind == "activity"