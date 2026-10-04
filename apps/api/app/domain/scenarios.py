"""Typed scenario DSL and pure time-trigger evaluation over template expansion."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union, Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError as PydanticValidationError, field_validator

from app.domain.expander import Segment, expand
from app.domain.models import Availability, TravelPhase, VisibilitySpec, WeekPattern


class TimeTrigger(BaseModel):
    kind: Literal["time"]
    days: List[int] = Field(default_factory=list)
    start_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_local: str = Field(pattern=r"^\d{2}:\d{2}$")
    week_pattern: WeekPattern = WeekPattern.EVERY
    active_from: Optional[str] = None
    active_to: Optional[str] = None

    @field_validator("days")
    @classmethod
    def validate_days(cls, days: List[int]) -> List[int]:
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("Scenario weekdays must be between 0 and 6")
        return days


class ActivityStateTrigger(BaseModel):
    kind: Literal["activity_state"]
    activity_type: str
    elapsed_min: int = Field(default=0, ge=0)


class BatteryTrigger(BaseModel):
    kind: Literal["battery"]
    threshold_pct: int = Field(ge=0, le=100)


class ManualTrigger(BaseModel):
    kind: Literal["manual"]


ScenarioTrigger = Annotated[
    Union[TimeTrigger, ActivityStateTrigger, BatteryTrigger, ManualTrigger],
    Field(discriminator="kind"),
]


class ScenarioCondition(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gte", "lte", "contains"]
    value: Any


class SetActivityEffect(BaseModel):
    kind: Literal["set_activity"]
    activity_type: str
    title: str
    availability: Availability = Field(default_factory=Availability)
    visibility: VisibilitySpec = Field(default_factory=VisibilitySpec)


class SetAvailabilityEffect(BaseModel):
    kind: Literal["set_availability"]
    availability: Availability


class SuppressNotificationsEffect(BaseModel):
    kind: Literal["suppress_notifications"]
    kinds: List[str] = Field(default_factory=list)


class NotifyEffect(BaseModel):
    kind: Literal["notify"]
    notification_kind: str


class CreateReminderEffect(BaseModel):
    kind: Literal["create_reminder"]
    title: str


ScenarioEffect = Annotated[
    Union[
        SetActivityEffect,
        SetAvailabilityEffect,
        SuppressNotificationsEffect,
        NotifyEffect,
        CreateReminderEffect,
    ],
    Field(discriminator="kind"),
]


class ScenarioDefinition(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    name: str
    enabled: bool = True
    trigger: ScenarioTrigger
    conditions: List[ScenarioCondition] = Field(default_factory=list)
    effects: List[ScenarioEffect]
    audience: List[str] = Field(default_factory=list)
    audience_mode: Literal["all_granted", "only", "except"] = "all_granted"
    notification_rule: Literal["always", "first_only", "never", "only_if_called"] = "always"
    priority: int = 50
    last_fired_at: Optional[datetime] = None


def _specificity(scenario: ScenarioDefinition) -> int:
    trigger = scenario.trigger
    return len(scenario.conditions) * 10 + (8 - len(trigger.days) if isinstance(trigger, TimeTrigger) and trigger.days else 0)


def _restrictiveness(activity: SetActivityEffect) -> int:
    calls = {"no": 2, "prefer_not": 1, "ok": 0}.get(activity.availability.calls.value, 0)
    messages = {"later": 1, "ok": 0}.get(activity.availability.messages.value, 0)
    return calls + messages


def resolve_time_scenarios(
    scenarios: List[Dict[str, Any]],
    now: datetime,
    tz: str,
) -> tuple[Optional[Dict[str, Any]], Optional[datetime]]:
    """Return the winning active scenario effect and earliest future time boundary."""
    local_date = now.astimezone(ZoneInfo(tz)).date()
    candidates = []
    boundaries = []

    for raw in scenarios:
        try:
            scenario = ScenarioDefinition.model_validate(raw)
        except PydanticValidationError:
            continue
        if not scenario.enabled or not isinstance(scenario.trigger, TimeTrigger):
            continue
        activity_effect = next(
            (effect for effect in scenario.effects if isinstance(effect, SetActivityEffect)),
            None,
        )
        if not activity_effect:
            continue

        trigger = scenario.trigger
        template = {
            "_id": scenario.id or scenario.name,
            "kind": "SCENARIO_TIME",
            "title": activity_effect.title,
            "activity_type": activity_effect.activity_type,
            "days": trigger.days,
            "start_local": trigger.start_local,
            "end_local": trigger.end_local,
            "week_pattern": trigger.week_pattern.value,
            "active_from": trigger.active_from,
            "active_to": trigger.active_to,
            "availability": activity_effect.availability.model_dump(mode="json"),
            "visibility": activity_effect.visibility.model_dump(mode="json"),
        }
        for day_offset in range(8):
            occurrence_date = local_date + timedelta(days=day_offset)
            segments = expand([template], [], [], occurrence_date, tz)
            active_segment = next(
                (segment for segment in segments if segment.start <= now < segment.end),
                None,
            )
            if active_segment:
                candidates.append((
                    scenario.priority,
                    _specificity(scenario),
                    _restrictiveness(activity_effect),
                    scenario.name,
                    active_segment,
                    activity_effect,
                    scenario,
                ))
            boundaries.extend(
                boundary
                for segment in segments
                for boundary in (segment.start, segment.end)
                if boundary > now
            )

    winning = max(candidates, key=lambda item: item[:3], default=None)
    active = None
    if winning:
        _, _, _, _, segment, effect, scenario = winning
        active = {
            "_id": scenario.id or scenario.name,
            "type": effect.activity_type,
            "title": effect.title,
            "status": "ACTIVE",
            "phase": TravelPhase.PLANNED.value,
            "start_at": segment.start,
            "expected_end_at": segment.end,
            "availability": effect.availability.model_dump(mode="python"),
            "visibility": effect.visibility.model_dump(mode="python"),
            "provenance": {"source": "system_inferred"},
            "scenario_id": scenario.id or scenario.name,
            "scenario_effects": [effect.model_dump(mode="python")]
            + [item.model_dump(mode="python") for item in scenario.effects if not isinstance(item, SetActivityEffect)],
            "notification_rule": scenario.notification_rule,
            "audience": scenario.audience,
            "audience_mode": scenario.audience_mode,
        }
    next_boundary = min(boundaries, default=None)
    return active, next_boundary