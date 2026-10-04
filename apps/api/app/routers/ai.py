"""Authenticated AI draft endpoints. Parsing never persists domain records."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo

import sentry_sdk
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.schemas import (
    ActivityDraft, DraftItem, ExceptionDraft, MessageDraft, PhoneDraft,
    ReminderDraft, ScenarioDraft, TimeSpec, TravelDraft,
)
from app.ai.service import AIService
from app.ai.timeparse import resolve_time_spec
from app.clock import get_clock
from app.core.errors import ForbiddenError, NotFoundError, StateConflictError, ValidationError
from app.core.ratelimit import ai_parse_limiter
from app.core.security import get_current_user_id
from app.db import get_db
from app.domain.visibility import ai_context_for_owner
from app.routers.cards import create_card, create_schedule_exception
from app.routers.scenarios import ScenarioWriteRequest, create_scenario

router = APIRouter(prefix="/ai", tags=["ai"])


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal["activity", "travel", "phone", "exception", "scenario", "message", "reminder"] = "activity"
    client_now: Optional[datetime] = None
    tz: Optional[str] = Field(default=None, max_length=50)


class ConfirmRequest(BaseModel):
    draft_id: str
    items: List[DraftItem] = Field(min_length=1)


@router.post("/parse")
async def parse_draft(
    payload: ParseRequest,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    ai_parse_limiter.check(current_user_id)
    db = get_db()
    owner = await db.users.find_one({"_id": current_user_id})
    if not owner:
        raise NotFoundError("User not found")

    now = clock.now()
    tz = payload.tz or owner.get("tz", "UTC")
    context = await ai_context_for_owner(db, current_user_id)
    service = AIService()
    with sentry_sdk.start_span(op="ai.parse", name="ai.parse") as span:
        outcome = await service.parse(
            text=payload.text,
            mode=payload.mode,
            now=now,
            tz=tz,
            connections=context["connections"],
            template_titles=context["template_titles"],
        )
        span.set_data("provider", outcome.provider)
        span.set_data("model", outcome.model)
        span.set_data("latency_ms", outcome.latency_ms)
        span.set_data("schema_valid", outcome.schema_valid)
        span.set_data("repaired", outcome.repaired)
        span.set_data("intent", outcome.result.intent)
        span.set_data("item_count", len(outcome.result.items))

    invocation = {
        "_id": str(ObjectId()),
        "user": current_user_id,
        "task": "parse",
        "model": outcome.model,
        "provider": outcome.provider,
        "latency_ms": outcome.latency_ms,
        "schema_valid": outcome.schema_valid,
        "repaired": outcome.repaired,
        "confirmed": False,
        "at": now,
    }
    if owner.get("ai_prefs", {}).get("store_raw", False):
        invocation["raw_text"] = payload.text
    await db.ai_invocations.insert_one(invocation)

    return {
        "draft_id": invocation["_id"],
        **outcome.result.model_dump(mode="json"),
    }


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_drafts(
    payload: ConfirmRequest,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    invocation = await db.ai_invocations.find_one({
        "_id": payload.draft_id,
        "user": current_user_id,
        "task": "parse",
    })
    if not invocation:
        raise NotFoundError("AI draft not found")
    if invocation.get("confirmed"):
        raise StateConflictError("AI draft was already confirmed")
    unsupported = [item.kind for item in payload.items if isinstance(item, ReminderDraft)]
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Reminder confirmation is implemented by a later module",
        )

    now = clock.now()
    owner = await db.users.find_one({"_id": current_user_id})
    if not owner:
        raise NotFoundError("User not found")
    tz = owner.get("tz", "UTC")
    provenance = {
        "source": "ai_parsed_user_confirmed",
        "model": invocation.get("model"),
        "confirmed_at": now,
    }
    records: List[Dict[str, Any]] = []
    weekday_numbers = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    for item in payload.items:
        if isinstance(item, ActivityDraft):
            card_payload: Dict[str, Any] = {
                "type": item.activity_type,
                "title": item.title,
                "availability": item.availability.model_dump(),
                "visibility": item.visibility.model_dump(),
                "provenance": provenance,
            }
            if item.resolved_start_at:
                card_payload["start_at"] = item.resolved_start_at
            if item.resolved_end_at:
                card_payload["expected_end_at"] = item.resolved_end_at
            created = await create_card("live", card_payload, current_user_id, clock)
        elif isinstance(item, TravelDraft):
            if not item.destination:
                raise ValidationError("Travel destination is required before confirmation")
            if not item.resolved_eta_at and not item.resolved_depart_at:
                raise ValidationError("Travel ETA or departure time is required before confirmation")
            metadata = {
                "destination": item.destination,
                "destination_kind": item.destination_kind,
                "mode": item.mode,
                "companions": [item.companion_id or item.companion] if (item.companion_id or item.companion) else [],
                "vehicle_number": item.vehicle_number,
                "driver_name": item.driver_name,
                "driver_phone": item.driver_phone,
            }
            if item.resolved_eta_at:
                metadata["eta"] = item.resolved_eta_at
            if item.expected_offline_window:
                metadata["expected_offline_window"] = {
                    key: value.model_dump() for key, value in item.expected_offline_window.items()
                }
            card_payload = {
                "type": "TRAVEL",
                "title": item.title,
                "metadata": metadata,
                "provenance": provenance,
                "check_on_me": {
                    "enabled": item.check_on_me,
                    "grace_min": 15,
                    "escalate_min": 15,
                },
            }
            if item.resolved_depart_at:
                card_payload["start_at"] = item.resolved_depart_at
            if item.resolved_eta_at:
                card_payload["expected_end_at"] = item.resolved_eta_at
            created = await create_card("travel", card_payload, current_user_id, clock)
        elif isinstance(item, PhoneDraft):
            card_payload = {
                "provenance": provenance,
                "may_go_offline": item.may_go_offline,
                "declared_offline": item.declared_offline,
            }
            for field in ("battery_pct", "mode", "calls", "messages"):
                value = getattr(item, field)
                if value is not None:
                    card_payload[field] = value
            created = await create_card("phone", card_payload, current_user_id, clock)
        elif isinstance(item, MessageDraft):
            card_payload = {
                "text": item.text,
                "template_key": item.template_key,
                "audience": item.audience,
            }
            if item.resolved_promise_at:
                card_payload["promise_at"] = item.resolved_promise_at
            created = await create_card("message", card_payload, current_user_id, clock)
        elif isinstance(item, ExceptionDraft):
            local_date = (
                datetime.fromisoformat(item.resolved_date).astimezone(ZoneInfo(tz)).date().isoformat()
                if item.resolved_date else now.astimezone(ZoneInfo(tz)).date().isoformat()
            )
            exception_payload: Dict[str, Any] = {
                "kind": item.exception_kind.value,
                "date": local_date,
                "template_id": item.template_id,
                "note": item.note,
            }
            for source_field, destination_field in (
                ("resolved_new_start", "new_start"),
                ("resolved_new_end", "new_end"),
            ):
                resolved_value = getattr(item, source_field)
                if resolved_value:
                    exception_payload[destination_field] = datetime.fromisoformat(
                        resolved_value
                    ).astimezone(ZoneInfo(tz)).strftime("%H:%M")
            created = await create_schedule_exception(exception_payload, current_user_id, clock)
        elif isinstance(item, ScenarioDraft):
            trigger_data = dict(item.trigger)
            if trigger_data.get("kind") == "time":
                weekday = trigger_data.get("weekday")
                days = trigger_data.get("days")
                if not days and weekday:
                    day_number = weekday_numbers.get(str(weekday).casefold())
                    if day_number is None:
                        raise ValidationError("Scenario weekday is invalid")
                    days = [day_number]
                local_times = {}
                for field in ("start", "end"):
                    time_value = trigger_data.get(field)
                    if not isinstance(time_value, dict):
                        raise ValidationError("Time scenario requires start and end times")
                    spec = TimeSpec.model_validate(time_value)
                    local_times[field] = resolve_time_spec(spec, now, tz).astimezone(
                        ZoneInfo(tz)
                    ).strftime("%H:%M")
                trigger_data = {
                    "kind": "time",
                    "days": days or [],
                    "start_local": local_times["start"],
                    "end_local": local_times["end"],
                    "week_pattern": trigger_data.get("week_pattern", "every"),
                }
            normalized_effects = []
            for effect in item.effects:
                if effect.get("kind") == "activity":
                    normalized_effects.append({
                        "kind": "set_activity",
                        "activity_type": effect.get("activity_type", "CUSTOM"),
                        "title": effect.get("title", item.name),
                        "availability": {
                            "calls": effect.get("calls", "ok"),
                            "messages": effect.get("messages", "ok"),
                        },
                    })
                elif effect.get("kind") == "suppress_notification":
                    normalized_effects.append({
                        "kind": "suppress_notifications",
                        "kinds": [effect.get("notification", "FREE_NOW")],
                    })
                else:
                    normalized_effects.append(effect)
            scenario_payload = ScenarioWriteRequest(
                name=item.name,
                trigger=trigger_data,
                conditions=item.conditions,
                effects=normalized_effects,
                audience=item.audience,
                audience_mode=item.audience_mode,
                notification_rule=item.notification_rule,
                priority=item.priority,
            )
            created = await create_scenario(scenario_payload, current_user_id, clock)
        else:
            raise ValidationError("Unsupported draft item")
        records.append(created)

    await db.ai_invocations.update_one(
        {"_id": payload.draft_id, "user": current_user_id, "confirmed": False},
        {"$set": {"confirmed": True, "confirmed_at": now}},
    )
    return {"draft_id": payload.draft_id, "records": records}