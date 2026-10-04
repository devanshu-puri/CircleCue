from datetime import date, datetime, timezone
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from pymongo.asynchronous.database import AsyncDatabase

from app.domain.models import (
    ResolvedState, ViewerState, Grant, AccessLevel, CardKey, ActivityType,
    ReachabilityResolved, ContextSnapshot, VisibilitySpec,
)
from app.domain.resolver import UserBundle, resolve
from app.domain.expander import expand

def is_grant_active(grant: Optional[Grant], now: datetime) -> bool:
    if not grant:
        return False
    if grant.revoked_at is not None:
        return False
    if grant.expires_at is not None and grant.expires_at <= now:
        return False
    return True


async def profile_by_code(db: AsyncDatabase, user_code: str) -> Optional[Dict[str, Any]]:
    user = await db.users.find_one({"user_code": user_code})
    if not user:
        return None
    return {
        "id": str(user["_id"]),
        "user_code": user["user_code"],
        "name": user["name"],
        "avatar_url": user.get("avatar_url"),
    }


async def connected_profile(db: AsyncDatabase, user_id: str) -> Optional[Dict[str, Any]]:
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return None
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "avatar_url": user.get("avatar_url"),
    }


async def ai_context_for_owner(
    db: AsyncDatabase,
    owner_id: str,
) -> Dict[str, List[Dict[str, str]]]:
    connection_docs = await db.connections.find({
        "status": "active",
        "$or": [{"a": owner_id}, {"b": owner_id}],
    }).to_list(length=1000)
    connections = []
    for connection in connection_docs:
        other_id = connection["b"] if connection["a"] == owner_id else connection["a"]
        profile = await connected_profile(db, other_id)
        if profile:
            connections.append({
                "id": profile["id"],
                "name": profile["name"].split()[0],
            })
    templates = await db.templates.find({"owner": owner_id}).to_list(length=1000)
    return {
        "connections": connections,
        "template_titles": [template.get("title", "") for template in templates],
    }

def can_view(grant: Optional[Grant], card: CardKey, required_level: AccessLevel, now: datetime) -> bool:
    if not is_grant_active(grant, now):
        return False
    
    granted_level = getattr(grant.cards, card.value, AccessLevel.NONE)
    if granted_level == AccessLevel.NONE:
        return False
    if required_level == AccessLevel.STATUS:
        return granted_level in (AccessLevel.STATUS, AccessLevel.DETAILS)
    if required_level == AccessLevel.DETAILS:
        return granted_level == AccessLevel.DETAILS
    return False


async def can_view_for_connection(
    db: AsyncDatabase,
    owner_id: str,
    viewer_id: str,
    card: CardKey,
    required_level: AccessLevel,
    now: datetime,
) -> bool:
    connection = await db.connections.find_one({
        "status": "active",
        "$or": [
            {"a": owner_id, "b": viewer_id},
            {"a": viewer_id, "b": owner_id},
        ],
    })
    if not connection:
        return False
    grant_doc = await db.grants.find_one({"owner": owner_id, "viewer": viewer_id})
    grant = Grant.model_validate(grant_doc) if grant_doc else None
    return can_view(grant, card, required_level, now)

def activity_card_for_type(act_type: ActivityType) -> CardKey:
    if act_type in (ActivityType.CLASS, ActivityType.LAB, ActivityType.BREAK, ActivityType.LUNCH, ActivityType.FREE_PERIOD):
        return CardKey.SCHEDULE
    elif act_type == ActivityType.EXAM:
        return CardKey.EXAM
    elif act_type == ActivityType.TRAVEL:
        return CardKey.TRAVEL
    elif act_type == ActivityType.PHONE_STATUS:
        return CardKey.PHONE
    elif act_type == ActivityType.SAFETY:
        return CardKey.SAFETY
    else:
        return CardKey.LIVE

def project(
    resolved: ResolvedState,
    grant: Optional[Grant],
    now: datetime,
    viewer_id: str
) -> ViewerState:
    """Single Visibility Choke Point. Redacts ResolvedState for a specific viewer according to grants."""
    
    # Missing, mismatched, revoked, or expired grants receive zero access.
    if (
        not is_grant_active(grant, now)
        or grant.owner != resolved.owner
        or grant.viewer != viewer_id
    ):
        return ViewerState(
            owner=resolved.owner,
            as_of=resolved.as_of,
            sharing_paused=False,
            activity=None,
            reachability=None,
            phone=None,
            current_place=None,
            card_access={},
            messages=[],
            travel=None,
            exam=None,
            last_shared_context=None,
            next_boundary_at=None
        )

    # An active grant holder sees a neutral pause state without context.
    if resolved.sharing_paused:
        return ViewerState(
            owner=resolved.owner,
            as_of=resolved.as_of,
            sharing_paused=True,
            activity={"type": "BUSY", "label": "Sharing paused", "until": None},
            reachability=None,
            phone=None,
            current_place=None,
            card_access={},
            messages=[],
            travel=None,
            exam=None,
            last_shared_context=None,
            next_boundary_at=None
        )

    # 3. Project Activity
    projected_activity: Optional[Dict[str, Any]] = None
    if resolved.activity:
        act = resolved.activity
        card = activity_card_for_type(act.type)
        card_level = getattr(grant.cards, card.value, AccessLevel.NONE)
        
        if card_level != AccessLevel.NONE:
            label = act.label
            # Check private label or override
            if act.provenance and hasattr(act, "visibility"):
                vis = getattr(act, "visibility", None)
                if vis:
                    if vis.mode == "only" and viewer_id not in vis.viewer_ids:
                        card_level = AccessLevel.NONE
                    elif vis.mode == "private_label" or vis.label_override:
                        label = vis.label_override or "Busy"

            if card_level == AccessLevel.STATUS:
                projected_activity = {
                    "type": act.type.value,
                    "label": label,
                    "until": act.until.isoformat() if act.until else None,
                    "layer": act.layer
                }
            elif card_level == AccessLevel.DETAILS:
                projected_activity = {
                    "type": act.type.value,
                    "label": label,
                    "until": act.until.isoformat() if act.until else None,
                    "layer": act.layer,
                    "provenance": act.provenance.model_dump()
                }

    # 4. Project Reachability
    projected_reachability: Optional[ReachabilityResolved] = None
    if grant.cards.live != AccessLevel.NONE or grant.cards.schedule != AccessLevel.NONE:
        projected_reachability = resolved.reachability

    # 5. Project Phone State
    projected_phone: Optional[Dict[str, Any]] = None
    phone_level = grant.cards.phone
    if phone_level != AccessLevel.NONE and resolved.phone:
        if phone_level == AccessLevel.STATUS:
            projected_phone = {
                "mode": resolved.phone.get("mode", "normal"),
                "battery_bucket": resolved.phone.get("battery_bucket", "ok"),
                "may_go_offline": resolved.phone.get("may_go_offline", False),
                "declared_offline": resolved.phone.get("declared_offline", False)
            }
        elif phone_level == AccessLevel.DETAILS:
            projected_phone = dict(resolved.phone)

    # 6. Project Travel State
    projected_travel: Optional[Dict[str, Any]] = None
    travel_level = grant.cards.travel
    if travel_level != AccessLevel.NONE and resolved.travel:
        if travel_level == AccessLevel.STATUS:
            projected_travel = {
                "destination_kind": resolved.travel.get("destination_kind", "other"),
                "eta": resolved.travel.get("eta"),
                "phase": resolved.travel.get("phase", "planned"),
                "overdue": resolved.travel.get("overdue", False)
            }
        elif travel_level == AccessLevel.DETAILS:
            projected_travel = dict(resolved.travel)

    # 7. Project Exam State
    projected_exam: Optional[Dict[str, Any]] = None
    exam_level = grant.cards.exam
    if exam_level != AccessLevel.NONE and resolved.exam:
        if exam_level == AccessLevel.STATUS:
            projected_exam = {
                "state": resolved.exam.get("state", "upcoming"),
                "until": resolved.exam.get("until"),
                "exams_today": resolved.exam.get("exams_today", 1)
            }
        elif exam_level == AccessLevel.DETAILS:
            projected_exam = dict(resolved.exam)

    has_visible_boundary = any((
        projected_activity is not None,
        resolved.current_place is not None and grant.cards.travel == AccessLevel.DETAILS,
        projected_reachability is not None,
        projected_travel is not None,
        projected_exam is not None,
    ))
    context_packet_visible = can_view(
        grant, CardKey.SAFETY, AccessLevel.DETAILS, now
    )

    return ViewerState(
        owner=resolved.owner,
        as_of=resolved.as_of,
        sharing_paused=False,
        activity=projected_activity,
        reachability=projected_reachability,
        phone=projected_phone,
        current_place=(resolved.current_place if travel_level == AccessLevel.DETAILS else None),
        card_access=grant.cards.model_dump(mode="json"),
        travel=projected_travel,
        exam=projected_exam,
        last_shared_context=(
            resolved.last_shared_context if context_packet_visible else None
        ),
        next_boundary_at=(
            resolved.next_boundary_at if has_visible_boundary else None
        )
    )

async def state_for_viewer(
    db: AsyncDatabase,
    owner_id: str,
    viewer_id: str,
    now: datetime,
) -> Optional[ViewerState]:
    """Load and project another user's state after verifying their active connection."""
    connection = await db.connections.find_one({
        "status": "active",
        "$or": [
            {"a": owner_id, "b": viewer_id},
            {"a": viewer_id, "b": owner_id},
        ],
    })
    if not connection:
        return None

    grant_doc = await db.grants.find_one({"owner": owner_id, "viewer": viewer_id})
    grant = Grant.model_validate(grant_doc) if grant_doc else None
    if not is_grant_active(grant, now):
        return project(ResolvedState(owner=owner_id, as_of=now), grant, now, viewer_id)

    resolved = await resolved_state_for_owner(db, owner_id, now)
    if not resolved:
        return None
    viewer_state = project(resolved, grant, now, viewer_id)
    message_level = grant.cards.message
    if (
        not viewer_state.sharing_paused
        and message_level != AccessLevel.NONE
    ):
        message_docs = await db.messages.find({"owner": owner_id}).to_list(length=1000)
        visible_messages = []
        for message in message_docs:
            expires_at = message.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at is None or expires_at <= now:
                continue
            audience = message.get("audience")
            if not audience and message_level != AccessLevel.DETAILS:
                continue
            if audience and viewer_id not in audience:
                continue
            projected_message = {
                "id": str(message.get("_id", "")),
                "expires_at": expires_at.isoformat(),
            }
            if message_level == AccessLevel.DETAILS:
                projected_message["text"] = message.get("text", "")
                if message.get("promise_at"):
                    promise_at = message["promise_at"]
                    projected_message["promise_at"] = (
                        promise_at.isoformat() if isinstance(promise_at, datetime) else promise_at
                    )
            visible_messages.append(projected_message)
        viewer_state.messages = visible_messages
    return viewer_state


async def resolved_state_for_owner(
    db: AsyncDatabase,
    owner_id: str,
    now: datetime,
    phone_state_override: Optional[Dict[str, Any]] = None,
) -> Optional[ResolvedState]:
    """Load one owner's inputs and resolve them without exposing raw records to routers."""
    user = await db.users.find_one({"_id": owner_id})
    if not user:
        return None

    activities = await db.activities.find({
        "owner": owner_id,
        "status": {"$nin": ["COMPLETED", "CANCELLED"]},
    }).to_list(length=500)
    templates = await db.templates.find({"owner": owner_id}).to_list(length=500)
    exceptions = await db.exceptions.find({"owner": owner_id}).to_list(length=500)
    exam_sets = await db.exam_sets.find({"owner": owner_id}).to_list(length=500)
    scenarios = await db.scenarios.find({
        "owner": owner_id,
        "enabled": True,
    }).to_list(length=200)

    bundle = UserBundle(
        owner_id=owner_id,
        tz=user.get("tz", "UTC"),
        routine_prefs=user.get("routine_prefs", {}),
        sharing_paused=user.get("sharing_paused", {}),
        activities=activities,
        templates=templates,
        exceptions=exceptions,
        exam_sets=exam_sets,
        phone_state=(
            phone_state_override
            if phone_state_override is not None
            else await db.phone_state.find_one({"_id": owner_id})
        ),
        scenarios=scenarios,
    )
    return resolve(bundle, now)


async def timeline_for_viewer(
    db: AsyncDatabase,
    owner_id: str,
    viewer_id: str,
    now: datetime,
    target_date: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """Return schedule-status fields only for an active, authorized connection."""
    connection = await db.connections.find_one({
        "status": "active",
        "$or": [
            {"a": owner_id, "b": viewer_id},
            {"a": viewer_id, "b": owner_id},
        ],
    })
    if not connection:
        return None

    grant_doc = await db.grants.find_one({"owner": owner_id, "viewer": viewer_id})
    grant = Grant.model_validate(grant_doc) if grant_doc else None
    if not can_view(grant, CardKey.SCHEDULE, AccessLevel.STATUS, now):
        return None

    owner = await db.users.find_one({"_id": owner_id})
    if not owner:
        return None
    tz = owner.get("tz", "UTC")
    if target_date is None:
        target_date = now.astimezone(ZoneInfo(tz)).date()

    pause = owner.get("sharing_paused", {})
    if pause.get("active") and (
        pause.get("until") is None or pause["until"] > now
    ):
        return {"date": target_date.isoformat(), "tz": tz, "segments": [], "sharing_paused": True}

    templates = await db.templates.find({"owner": owner_id}).to_list(length=500)
    exceptions = await db.exceptions.find({"owner": owner_id}).to_list(length=500)
    exam_sets = await db.exam_sets.find({"owner": owner_id}).to_list(length=500)
    segments = expand(templates, exceptions, exam_sets, target_date, tz)
    projected_segments = []
    for segment in segments:
        visibility = VisibilitySpec.model_validate(segment.visibility or {})
        if visibility.mode == "only" and viewer_id not in visibility.viewer_ids:
            continue
        label = segment.label
        if visibility.mode == "private_label" or visibility.label_override:
            label = visibility.label_override or "Busy"
        projected_segments.append({
            "start": segment.start.isoformat(),
            "end": segment.end.isoformat(),
            "activity_type": segment.activity_type,
            "label": label,
            "calls_ok": segment.calls_ok,
            "calls": segment.call_preference,
        })

    return {
        "date": target_date.isoformat(),
        "tz": tz,
        "segments": projected_segments,
        "sharing_paused": False,
    }

async def viewers_for(
    db: AsyncDatabase,
    owner_id: str,
    card: CardKey,
    required_level: AccessLevel,
    now: datetime
) -> List[str]:
    """Return all active viewer IDs who have permission to view owner's card at required_level."""
    card_field = f"cards.{card.value}"
    
    query = {
        "owner": owner_id,
        "revoked_at": None,
        "$or": [
            {"expires_at": None},
            {"expires_at": {"$gt": now}}
        ]
    }
    
    if required_level == AccessLevel.STATUS:
        query[card_field] = {"$in": ["status", "details"]}
    elif required_level == AccessLevel.DETAILS:
        query[card_field] = "details"
    else:
        return []

    connection_cursor = db.connections.find({
        "status": "active",
        "$or": [{"a": owner_id}, {"b": owner_id}],
    })
    connections = await connection_cursor.to_list(length=1000)
    connected_viewers = {
        connection["b"] if connection["a"] == owner_id else connection["a"]
        for connection in connections
    }

    cursor = db.grants.find({"owner": owner_id})
    grant_docs = await cursor.to_list(length=1000)
    viewers = []
    for grant_doc in grant_docs:
        grant = Grant.model_validate(grant_doc)
        if (
            grant.viewer in connected_viewers
            and can_view(grant, card, required_level, now)
        ):
            viewers.append(grant.viewer)
    return viewers
