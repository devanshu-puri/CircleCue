"""Generic owner-only card routes backed by the shared CardSpec registry."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.clock import get_clock
from app.core.audit import log_audit_event
from app.core.errors import ForbiddenError, NotFoundError, StateConflictError, ValidationError
from app.core.security import get_current_user_id
from app.db import get_db
from app.domain.events import DomainEvent
from app.domain.notifications import publish_and_process
from app.domain.lifecycle_service import default_expected_end
from app.domain.lifecycle_service import transition
from app.domain.models import (
    AccessLevel, Activity, ActivityType, CardKey, ContextSnapshot,
    ExamSet, ExceptionItem, Message, PhoneState, Status, Template, TravelMeta,
    TravelPhase,
)
from app.domain.visibility import can_view_for_connection, resolved_state_for_owner, viewers_for
from app.cards.registry import CARD_REGISTRY

router = APIRouter(prefix="/cards", tags=["cards"])

MESSAGE_TEMPLATES = {
    "cant_talk": "Can't talk right now",
    "running_late": "Running late",
    "class_cancelled": "Class got cancelled",
    "someone_over": "Someone came over",
    "dinner": "Dinner at ...",
    "phone_dying": "Phone might die",
}


def _card_spec(key: str):
    try:
        card_key = CardKey(key.lower())
    except ValueError as exc:
        raise NotFoundError("Unknown card") from exc
    return CARD_REGISTRY[card_key]


def _routine_wake_at(start_at: datetime, tz: str, wake: str) -> datetime:
    local_start = start_at.astimezone(ZoneInfo(tz))
    hour, minute = int(wake[:2]), int(wake[3:5])
    wake_at = local_start.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if wake_at <= local_start:
        wake_at += timedelta(days=1)
    return wake_at.astimezone(timezone.utc)


def _battery_bucket(battery_pct: Any) -> str:
    if type(battery_pct) is not int or not 0 <= battery_pct <= 100:
        raise ValidationError("battery_pct must be an integer between 0 and 100")
    if battery_pct <= 5:
        return "dying"
    if battery_pct <= 10:
        return "critical"
    if battery_pct <= 20:
        return "low"
    return "ok"


async def _freeze_context_if_needed(
    db,
    owner_id: str,
    now: datetime,
    phone_record: Dict[str, Any],
) -> None:
    if not phone_record.get("may_go_offline") and phone_record.get("battery_pct", 100) > 10:
        return
    resolved = await resolved_state_for_owner(
        db, owner_id, now, phone_state_override=phone_record
    )
    if resolved:
        phone_record["last_shared_context"] = ContextSnapshot(
            snapshot=resolved.model_dump(mode="json", exclude={"last_shared_context"}),
            shared_at=now,
        ).model_dump(mode="python")


@router.get("/{key}")
async def list_cards(
    key: str,
    current_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    spec = _card_spec(key)
    if spec.record_model is PhoneState:
        phone = await db[spec.collection].find_one({"_id": current_user_id})
        return [phone] if phone else []

    records = await db[spec.collection].find({"owner": current_user_id}).to_list(length=1000)
    if spec.record_model is Template:
        expected_types = {activity_type.value for activity_type in spec.activity_types}
        records = [record for record in records if record.get("activity_type") in expected_types]
    elif spec.record_model is Activity:
        expected_types = {activity_type.value for activity_type in spec.activity_types}
        records = [record for record in records if record.get("type") in expected_types]
    return records


@router.get("/message/templates")
async def list_message_templates():
    return [{"key": key, "text": text} for key, text in MESSAGE_TEMPLATES.items()]


@router.post("/safety/context", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def share_safety_context_stub(
    current_user_id: str = Depends(get_current_user_id),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Expiring safety context packets are planned for P1",
    )


@router.post("/messages/{message_id}/reactions")
async def react_to_message(
    message_id: str,
    payload: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    reaction_text = payload.get("reaction")
    if reaction_text not in ("OK", "Call me later"):
        raise ValidationError("Unsupported quick reaction")

    db = get_db()
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise NotFoundError("Message not found")
    if current_user_id not in message.get("audience", []):
        raise ForbiddenError("Message was not shared with this user")

    now = clock.now()
    if not await can_view_for_connection(
        db,
        message["owner"],
        current_user_id,
        CardKey.MESSAGE,
        AccessLevel.DETAILS,
        now,
    ):
        raise ForbiddenError("Message details access is required")

    expected_version = payload.get("version")
    current_version = message.get("version", 1)
    if expected_version is None:
        raise ValidationError("Message reactions require the current version")
    if expected_version != current_version:
        raise StateConflictError("Message version is stale")

    reactions = [
        reaction for reaction in message.get("reactions", [])
        if reaction.get("user_id") != current_user_id
    ]
    reaction = {"user_id": current_user_id, "text": reaction_text, "at": now.isoformat()}
    reactions.append(reaction)
    result = await db.messages.update_one(
        {"_id": message_id, "owner": message["owner"], "version": current_version},
        {"$set": {"reactions": reactions, "version": current_version + 1}},
    )
    if not result.modified_count:
        raise StateConflictError("Message changed during reaction")

    await publish_and_process(db, DomainEvent(
        kind="MESSAGE_REACTION",
        owner=message["owner"],
        entity_id=message_id,
        after={"reaction": reaction_text},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="MESSAGE_REACTION",
        target=message_id,
        meta={"reaction": reaction_text},
    )
    return {"message_id": message_id, "reaction": reaction, "version": current_version + 1}


@router.get("/schedule/exceptions")
async def list_schedule_exceptions(
    current_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    return await db.exceptions.find({"owner": current_user_id}).to_list(length=1000)


@router.post("/schedule/exceptions", status_code=status.HTTP_201_CREATED)
async def create_schedule_exception(
    payload: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    data = {**payload, "owner": current_user_id, "_id": str(ObjectId())}
    try:
        exception = ExceptionItem.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError("Invalid schedule exception", details={"errors": exc.errors()}) from exc

    if exception.template_id:
        template = await db.templates.find_one({
            "_id": exception.template_id,
            "owner": current_user_id,
        })
        if not template:
            raise NotFoundError("Schedule template not found")

    record = exception.model_dump(mode="python", by_alias=True)
    await db.exceptions.insert_one(record)
    now = clock.now()
    await publish_and_process(db, DomainEvent(
        kind="SCHEDULE_CHANGED",
        owner=current_user_id,
        entity_id=record["_id"],
        after={"card": CardKey.SCHEDULE.value},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="SCHEDULE_EXCEPTION_CREATE",
        target=record["_id"],
        meta={"kind": exception.kind.value},
    )
    return record


@router.put("/schedule/bulk")
async def bulk_save_schedule(
    payload: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    templates = payload.get("templates")
    if not isinstance(templates, list):
        raise ValidationError("templates must be a list")

    db = get_db()
    collection = db.templates
    existing = await collection.find({"owner": current_user_id}).to_list(length=1000)
    existing_by_id = {str(record["_id"]): record for record in existing}
    now = clock.now()
    validated = []
    included_ids = set()

    for template_payload in templates:
        data = {**CARD_REGISTRY[CardKey.SCHEDULE].defaults, **template_payload}
        data["owner"] = current_user_id
        item_id = str(data.get("_id") or data.get("id") or ObjectId())
        if item_id in included_ids:
            raise ValidationError("Duplicate schedule template id")
        included_ids.add(item_id)
        data.pop("id", None)
        data["_id"] = item_id

        prior = existing_by_id.get(item_id)
        if prior:
            expected_version = data.get("version")
            current_version = prior.get("version", 1)
            if expected_version is None:
                raise ValidationError("Existing schedule slots require their current version")
            if expected_version != current_version:
                raise StateConflictError("Schedule template version is stale")
            data["version"] = current_version + 1
        else:
            data["version"] = 1

        try:
            activity_type = ActivityType(data.get("activity_type"))
            if activity_type not in CARD_REGISTRY[CardKey.SCHEDULE].activity_types:
                raise ValidationError("Activity type does not belong to the schedule card")
            record = Template.model_validate(data).model_dump(mode="python", by_alias=True)
        except PydanticValidationError as exc:
            raise ValidationError("Invalid schedule template", details={"errors": exc.errors()}) from exc
        validated.append((item_id, prior, record))

    for item_id, prior, record in validated:
        if prior:
            result = await collection.update_one(
                {"_id": item_id, "owner": current_user_id, "version": prior.get("version", 1)},
                {"$set": record},
            )
            if not result.modified_count:
                raise StateConflictError("Schedule changed during bulk save")
        else:
            await collection.insert_one(record)

    for item_id, prior in existing_by_id.items():
        if item_id not in included_ids:
            await collection.delete_one({"_id": item_id, "owner": current_user_id})

    await publish_and_process(db, DomainEvent(
        kind="SCHEDULE_CHANGED",
        owner=current_user_id,
        entity_id="bulk",
        after={"card": CardKey.SCHEDULE.value, "count": len(validated)},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="SCHEDULE_BULK_SAVE",
        meta={"count": len(validated)},
    )
    return {"templates": [record for _, _, record in validated]}


@router.get("/exam/season")
async def exam_season_overview(
    current_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    exam_sets = await db.exam_sets.find({"owner": current_user_id}).to_list(length=1000)
    dates = []
    for exam_set in sorted(exam_sets, key=lambda item: item.get("date", "")):
        count = sum(
            1 for item in exam_set.get("items", [])
            if item.get("type") == "exam"
        )
        dates.append({
            "date": exam_set.get("date"),
            "exam_count": count,
            "two_exam_day": count >= 2,
        })
    return {
        "dates": dates,
        "exam_count": sum(item["exam_count"] for item in dates),
        "two_exam_days": [item["date"] for item in dates if item["two_exam_day"]],
    }


@router.post("/{key}", status_code=status.HTTP_201_CREATED)
async def create_card(
    key: str,
    payload: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    spec = _card_spec(key)
    now = clock.now()
    data = {**spec.defaults, **payload}

    if spec.record_model is PhoneState:
        data.pop("owner", None)
        data["_id"] = current_user_id
        data["updated_at"] = now
        data["battery_bucket"] = _battery_bucket(data.get("battery_pct", 100))
    else:
        data["owner"] = current_user_id
        data["_id"] = str(ObjectId())

    if spec.record_model is Template:
        try:
            activity_type = ActivityType(data.get("activity_type"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Unknown schedule activity type") from exc
        if activity_type not in spec.activity_types:
            raise ValidationError("Activity type does not belong to this card")

    if spec.record_model is Activity:
        try:
            activity_type = ActivityType(data.get("type"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Unknown activity type") from exc
        if activity_type not in spec.activity_types:
            raise ValidationError("Activity type does not belong to this card")
        data.setdefault("start_at", now)
        start_at = data["start_at"]
        if isinstance(start_at, str):
            start_at = datetime.fromisoformat(start_at)
        data.setdefault("provenance", {"source": "user_shared"})
        if activity_type == ActivityType.SLEEP and not data.get("expected_end_at"):
            owner = await db.users.find_one({"_id": current_user_id}) or {}
            wake_at = _routine_wake_at(
                start_at,
                owner.get("tz", "UTC"),
                owner.get("routine_prefs", {}).get("wake", "07:00"),
            )
            data["expected_end_at"] = default_expected_end(activity_type, start_at, wake_at)
        else:
            data.setdefault("expected_end_at", default_expected_end(activity_type, start_at))
        data["created_at"] = now
        data["updated_at"] = now
        if activity_type == ActivityType.TRAVEL:
            metadata = dict(data.get("metadata") or {})
            metadata.setdefault("mode", "cab")
            if not metadata.get("eta"):
                metadata["eta"] = data["expected_end_at"]
            try:
                data["metadata"] = TravelMeta.model_validate(metadata).model_dump(mode="python")
            except PydanticValidationError as exc:
                raise ValidationError("Invalid travel metadata", details={"errors": exc.errors()}) from exc
            data.setdefault("status", Status.PLANNED)
            data.setdefault("phase", TravelPhase.PLANNED)
        elif activity_type == ActivityType.SAFETY:
            check_on_me = dict(data.get("check_on_me") or {})
            check_on_me.setdefault("enabled", True)
            check_on_me.setdefault("grace_min", spec.defaults.get("grace_min", 15))
            check_on_me.setdefault("escalate_min", spec.defaults.get("escalate_min", 15))
            data["check_on_me"] = check_on_me

    if spec.record_model is Message:
        template_key = data.get("template_key")
        if template_key:
            template_text = MESSAGE_TEMPLATES.get(template_key)
            if not template_text:
                raise ValidationError("Unknown message template")
            data.setdefault("text", template_text)
        if not data.get("expires_at"):
            data["expires_at"] = now + timedelta(hours=12)
        if not data.get("audience"):
            # An empty audience is the UI's “all granted connections” option.
            data["audience"] = await viewers_for(
                db, current_user_id, CardKey.MESSAGE, AccessLevel.DETAILS, now
            )
        for viewer_id in data.get("audience", []):
            if not await can_view_for_connection(
                db,
                current_user_id,
                viewer_id,
                CardKey.MESSAGE,
                required_level=AccessLevel.DETAILS,
                now=now,
            ):
                raise ForbiddenError("Message audience must have message details access")

    try:
        model = spec.record_model.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError("Invalid card payload", details={"errors": exc.errors()}) from exc

    record = model.model_dump(mode="python", by_alias=True)
    record_id = str(record.get("_id") or current_user_id)
    record["_id"] = record_id

    if spec.record_model is PhoneState:
        await _freeze_context_if_needed(db, current_user_id, now, record)

    collection = db[spec.collection]
    if spec.record_model is PhoneState:
        existing = await collection.find_one({"_id": current_user_id})
        if existing:
            raise StateConflictError("Phone state already exists; update it with its current version")
        await collection.insert_one(record)
    elif spec.record_model is ExamSet:
        existing = await collection.find_one({"owner": current_user_id, "date": record["date"]})
        if existing:
            expected_version = payload.get("version")
            current_version = existing.get("version", 1)
            if expected_version is None:
                raise ValidationError("Exam-set updates require the current version")
            if expected_version != current_version:
                raise StateConflictError("Exam-set version is stale")
            record["_id"] = str(existing["_id"])
            record["version"] = current_version + 1
            record_id = record["_id"]
            result = await collection.update_one(
                {"_id": record_id, "owner": current_user_id, "version": current_version},
                {"$set": record},
            )
            if not result.modified_count:
                raise StateConflictError("Exam set changed during update")
        else:
            await collection.insert_one(record)
    else:
        await collection.insert_one(record)

    event_kinds = {
        CardKey.SCHEDULE: "SCHEDULE_CHANGED",
        CardKey.EXAM: "EXAM_SET_CHANGED",
        CardKey.LIVE: "ACTIVITY_STARTED",
        CardKey.PHONE: "PHONE_STATE_CHANGED",
        CardKey.MESSAGE: "MESSAGE_DROP",
        CardKey.SAFETY: "ARRIVAL_WATCH_STARTED",
    }
    event_kind = event_kinds.get(spec.key, "CARD_CREATED")
    if spec.key == CardKey.TRAVEL:
        is_departing = (
            record.get("status") == Status.ACTIVE
            and record.get("phase") == TravelPhase.TRAVELLING
        )
        event_kind = "TRAVEL_STARTED" if is_departing else "TRAVEL_PLANNED"
    await publish_and_process(db, DomainEvent(
        kind=event_kind,
        owner=current_user_id,
        entity_id=record_id,
        after={"card": spec.key.value},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="CARD_CREATE",
        target=record_id,
        meta={"card": spec.key.value},
    )
    return {"id": record_id, "card": spec.key.value, "record": record}


@router.get("/travel/{item_id}/return")
async def prefill_return_trip(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    activity = await db.activities.find_one({
        "_id": item_id,
        "owner": current_user_id,
        "type": ActivityType.TRAVEL.value,
    })
    if not activity:
        raise NotFoundError("Travel card not found")
    metadata = activity.get("metadata", {})
    return {
        "type": ActivityType.TRAVEL.value,
        "title": "Heading home",
        "status": Status.PLANNED.value,
        "phase": TravelPhase.PLANNED.value,
        "metadata": {
            "destination": "Home",
            "destination_kind": "home",
            "mode": metadata.get("mode", "cab"),
        },
    }


@router.patch("/{key}/{item_id}")
async def update_card(
    key: str,
    item_id: str,
    payload: Dict[str, Any],
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    spec = _card_spec(key)
    collection = db[spec.collection]
    query = {"_id": item_id, "owner": current_user_id}
    if spec.record_model is PhoneState:
        query = {"_id": current_user_id}
    existing = await collection.find_one(query)
    if not existing:
        raise NotFoundError("Card not found")

    now = clock.now()
    updates = dict(payload)
    if spec.record_model is Activity:
        expected_version = updates.pop("version", None)
        current_version = existing.get("version", 1)
        if expected_version is None:
            raise ValidationError("Activity updates require the current version")
        if expected_version != current_version:
            raise StateConflictError("Activity version is stale")

        current_status = Status(existing.get("status", Status.PLANNED.value))
        target_status = Status(updates.get("status", current_status.value))
        if "status" not in updates and current_status in (
            Status.ACTIVE, Status.EXTENDED, Status.DELAYED, Status.CHANGED,
        ):
            target_status = Status.CHANGED
        transition_payload = {k: v for k, v in updates.items() if k != "status"}
        updated = transition(
            existing,
            target_status,
            actor=current_user_id,
            now=now,
            payload=transition_payload,
            publish_event=False,
        )
        try:
            record = Activity.model_validate(updated).model_dump(mode="python", by_alias=True)
        except PydanticValidationError as exc:
            raise ValidationError("Invalid card update", details={"errors": exc.errors()}) from exc
        result = await collection.update_one(
            {"_id": item_id, "owner": current_user_id, "version": current_version},
            {"$set": record},
        )
        if not result.modified_count:
            raise StateConflictError("Activity changed during update")
        if spec.key == CardKey.TRAVEL:
            if target_status == Status.CANCELLED:
                event_kind = "ACTIVITY_CANCELLED"
            elif "new_eta" in transition_payload:
                event_kind = "TRAVEL_DELAYED"
            elif updated.get("phase") == TravelPhase.ARRIVED.value:
                event_kind = "TRAVEL_ARRIVED"
            elif (
                current_status == Status.PLANNED
                and target_status == Status.ACTIVE
                and updated.get("phase") == TravelPhase.TRAVELLING.value
            ):
                event_kind = "TRAVEL_STARTED"
            else:
                event_kind = "PLAN_CHANGED"
        else:
            event_kind = (
                "ACTIVITY_CANCELLED" if target_status == Status.CANCELLED
                else "ACTIVITY_CHANGED"
            )
    else:
        expected_version = updates.pop("version", None)
        current_version = existing.get("version", 1)
        if expected_version is None:
            raise ValidationError("Card updates require the current version")
        if expected_version != current_version:
            raise StateConflictError("Card version is stale")
        merged = {**existing, **updates}
        merged["version"] = current_version + 1
        if spec.record_model is Message and not merged.get("audience"):
            merged["audience"] = await viewers_for(
                db, current_user_id, CardKey.MESSAGE, AccessLevel.DETAILS, now
            )
        if spec.record_model is PhoneState:
            merged.pop("owner", None)
            merged["_id"] = current_user_id
            merged["updated_at"] = now
            merged["battery_bucket"] = _battery_bucket(merged.get("battery_pct", 100))
        else:
            merged["owner"] = current_user_id
            merged["_id"] = item_id
        try:
            record = spec.record_model.model_validate(merged).model_dump(
                mode="python", by_alias=True
            )
        except PydanticValidationError as exc:
            raise ValidationError("Invalid card update", details={"errors": exc.errors()}) from exc
        if spec.record_model is PhoneState:
            await _freeze_context_if_needed(db, current_user_id, now, record)
        version_query = {**query, "version": current_version}
        result = await collection.update_one(version_query, {"$set": record})
        if not result.modified_count:
            raise NotFoundError("Card not found")
        event_kind = {
            CardKey.SCHEDULE: "SCHEDULE_CHANGED",
            CardKey.EXAM: "EXAM_SET_CHANGED",
            CardKey.PHONE: "PHONE_STATE_CHANGED",
            CardKey.MESSAGE: "MESSAGE_DROP",
        }.get(spec.key, "CARD_CHANGED")

    await publish_and_process(db, DomainEvent(
        kind=event_kind,
        owner=current_user_id,
        entity_id=item_id,
        after={"card": spec.key.value},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="CARD_UPDATE",
        target=item_id,
        meta={"card": spec.key.value},
    )
    return {"id": item_id, "card": spec.key.value, "record": record}


@router.delete("/{key}/{item_id}")
async def delete_card(
    key: str,
    item_id: str,
    expected_version: int | None = Query(default=None, alias="version"),
    current_user_id: str = Depends(get_current_user_id),
    clock=Depends(get_clock),
):
    db = get_db()
    spec = _card_spec(key)
    collection = db[spec.collection]
    query = {"_id": item_id, "owner": current_user_id}
    if spec.record_model is PhoneState:
        query = {"_id": current_user_id}
    existing = await collection.find_one(query)
    if not existing:
        raise NotFoundError("Card not found")

    now = clock.now()
    if spec.record_model is Activity:
        current_version = existing.get("version", 1)
        if expected_version is None:
            raise ValidationError("Activity cancellation requires the current version")
        if expected_version != current_version:
            raise StateConflictError("Activity version is stale")
        updated = transition(
            existing,
            Status.CANCELLED,
            actor=current_user_id,
            now=now,
            publish_event=False,
        )
        result = await collection.update_one(
            {"_id": item_id, "owner": current_user_id, "version": current_version},
            {"$set": updated},
        )
        if not result.modified_count:
            raise StateConflictError("Activity changed during cancellation")
        event_kind = "ACTIVITY_CANCELLED"
    else:
        current_version = existing.get("version", 1)
        if expected_version is None:
            raise ValidationError("Card deletion requires the current version")
        if expected_version != current_version:
            raise StateConflictError("Card version is stale")
        result = await collection.delete_one({**query, "version": current_version})
        if not result.deleted_count:
            raise StateConflictError("Card changed during deletion")
        event_kind = {
            CardKey.SCHEDULE: "SCHEDULE_CHANGED",
            CardKey.EXAM: "EXAM_SET_CHANGED",
            CardKey.PHONE: "PHONE_STATE_CHANGED",
            CardKey.MESSAGE: "MESSAGE_DROP",
        }.get(spec.key, "CARD_DELETED")

    await publish_and_process(db, DomainEvent(
        kind=event_kind,
        owner=current_user_id,
        entity_id=item_id,
        before={"card": spec.key.value},
        occurred_at=now,
    ), now)
    await log_audit_event(
        actor=current_user_id,
        action="CARD_DELETE",
        target=item_id,
        meta={"card": spec.key.value},
    )
    return {"message": "Card deleted"}
