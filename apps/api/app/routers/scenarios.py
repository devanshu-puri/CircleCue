"""Owner-controlled custom scenario CRUD and safe dry-run preview."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from app.clock import get_clock
from app.core.audit import log_audit_event
from app.core.errors import NotFoundError, StateConflictError, ValidationError
from app.core.security import get_current_user_id
from app.db import get_db
from app.domain.events import DomainEvent
from app.domain.models import ActivityType, CardKey, Scenario
from app.domain.notifications import publish_and_process
from app.domain.scenarios import (
    ScenarioCondition, ScenarioEffect, ScenarioTrigger,
    resolve_time_scenarios,
)
from app.domain.visibility import connected_profile, viewers_for
from app.domain.visibility import activity_card_for_type
from app.domain.models import AccessLevel

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    trigger: ScenarioTrigger
    conditions: List[ScenarioCondition] = Field(default_factory=list)
    effects: List[ScenarioEffect]
    audience: List[str] = Field(default_factory=list)
    audience_mode: Literal["all_granted", "only", "except"] = "all_granted"
    notification_rule: Literal["always", "first_only", "never", "only_if_called"] = "always"
    priority: int = Field(default=50, ge=0, le=100)
    version: Optional[int] = None


def _scenario_document(owner_id: str, scenario_id: str, payload: ScenarioWriteRequest, version: int) -> Dict[str, Any]:
    return {
        "_id": scenario_id,
        "owner": owner_id,
        "name": payload.name,
        "enabled": payload.enabled,
        "trigger": payload.trigger.model_dump(mode="json"),
        "conditions": [condition.model_dump(mode="json") for condition in payload.conditions],
        "effects": [effect.model_dump(mode="json") for effect in payload.effects],
        "audience": payload.audience,
        "audience_mode": payload.audience_mode,
        "notification_rule": {"kind": payload.notification_rule},
        "priority": payload.priority,
        "version": version,
    }


def _validate_scenario(document: Dict[str, Any]) -> None:
    try:
        Scenario.model_validate(document)
    except PydanticValidationError as exc:
        raise ValidationError("Invalid scenario", details={"errors": exc.errors()}) from exc


@router.get("")
async def list_scenarios(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    return await db.scenarios.find({"owner": current_user_id}).to_list(length=1000)


@router.post("", status_code=201)
async def create_scenario(
    payload: ScenarioWriteRequest,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    scenario_id = str(ObjectId())
    document = _scenario_document(current_user_id, scenario_id, payload, 1)
    _validate_scenario(document)
    await db.scenarios.insert_one(document)
    now = clock.now()
    await publish_and_process(db, DomainEvent(
        kind="SCENARIO_CHANGED",
        owner=current_user_id,
        entity_id=scenario_id,
        after={"enabled": payload.enabled},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="SCENARIO_CREATE",
        target=scenario_id,
        meta={"trigger": payload.trigger.kind},
    )
    return document


@router.patch("/{scenario_id}")
async def update_scenario(
    scenario_id: str,
    payload: ScenarioWriteRequest,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    existing = await db.scenarios.find_one({"_id": scenario_id, "owner": current_user_id})
    if not existing:
        raise NotFoundError("Scenario not found")
    current_version = existing.get("version", 1)
    if payload.version is None:
        raise ValidationError("Scenario updates require the current version")
    if payload.version != current_version:
        raise StateConflictError("Scenario version is stale")
    document = _scenario_document(current_user_id, scenario_id, payload, current_version + 1)
    _validate_scenario(document)
    result = await db.scenarios.update_one(
        {"_id": scenario_id, "owner": current_user_id, "version": current_version},
        {"$set": document},
    )
    if not result.modified_count:
        raise StateConflictError("Scenario changed during update")
    now = clock.now()
    await publish_and_process(db, DomainEvent(
        kind="SCENARIO_CHANGED",
        owner=current_user_id,
        entity_id=scenario_id,
        after={"enabled": payload.enabled},
        occurred_at=now,
    ), now)
    await log_audit_event(actor=current_user_id, action="SCENARIO_UPDATE", target=scenario_id)
    return document


@router.delete("/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    version: int = Query(...),
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    result = await db.scenarios.delete_one({
        "_id": scenario_id,
        "owner": current_user_id,
        "version": version,
    })
    if not result.deleted_count:
        existing = await db.scenarios.find_one({"_id": scenario_id, "owner": current_user_id})
        if not existing:
            raise NotFoundError("Scenario not found")
        raise StateConflictError("Scenario version is stale")
    now = clock.now()
    await publish_and_process(db, DomainEvent(
        kind="SCENARIO_CHANGED",
        owner=current_user_id,
        entity_id=scenario_id,
        before={"deleted": True},
        occurred_at=now,
    ), now)
    await log_audit_event(actor=current_user_id, action="SCENARIO_DELETE", target=scenario_id)
    return {"message": "Scenario deleted"}


@router.post("/{scenario_id}/dry-run")
async def dry_run_scenario(
    scenario_id: str,
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    document = await db.scenarios.find_one({"_id": scenario_id, "owner": current_user_id})
    if not document:
        raise NotFoundError("Scenario not found")
    owner = await db.users.find_one({"_id": current_user_id})
    tz = owner.get("tz", "UTC") if owner else "UTC"
    now = clock.now()
    active, next_boundary = resolve_time_scenarios([document], now, tz)

    activity_effect = next((
        effect for effect in document.get("effects", [])
        if effect.get("kind") == "set_activity"
    ), None)
    card = activity_card_for_type(ActivityType(activity_effect["activity_type"])) if activity_effect else CardKey.LIVE
    granted = set(await viewers_for(db, current_user_id, card, AccessLevel.STATUS, now))
    configured = set(document.get("audience", []))
    mode = document.get("audience_mode", "all_granted")
    if mode == "only":
        requested = configured
        viewers = requested & granted
    elif mode == "except":
        requested = granted - configured
        viewers = requested
    else:
        requested = granted
        viewers = granted

    warnings = []
    for viewer_id in sorted(requested - granted):
        profile = await connected_profile(db, viewer_id)
        display_name = profile["name"].split()[0] if profile else "Selected user"
        warnings.append(f"{display_name} was excluded because no matching grant exists.")

    audience_names = []
    for viewer_id in sorted(viewers):
        profile = await connected_profile(db, viewer_id)
        if profile:
            audience_names.append(profile["name"].split()[0])

    starts_at = active.get("start_at") if active else next_boundary
    ends_at = active.get("expected_end_at") if active else None
    if active:
        summary = f"Would apply {active['title']} until {ends_at.isoformat()}."
    elif next_boundary:
        summary = f"Would next activate at {next_boundary.isoformat()}."
    else:
        summary = "No time-trigger occurrence is scheduled in the next week."

    return {
        "scenario_id": scenario_id,
        "is_active_now": active is not None,
        "would_fire": active is not None or next_boundary is not None,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "audience": audience_names,
        "effects": document.get("effects", []),
        "summary": summary,
        "warnings": warnings,
    }