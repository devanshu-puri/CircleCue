from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import get_db
from app.core.security import get_current_user_id
from app.core.errors import NotFoundError, ValidationError, ForbiddenError
from app.core.audit import log_audit_event
from app.domain.models import Grant, CardGrants, NotifyFlags, ConnectionStatus
from app.domain.visibility import connected_profile

router = APIRouter(prefix="/grants", tags=["grants"])

class GrantUpdateRequest(BaseModel):
    relationship_preset: Optional[str] = Field(default="friend", max_length=30)
    cards: CardGrants = Field(default_factory=CardGrants)
    notify: NotifyFlags = Field(default_factory=NotifyFlags)
    important: bool = False
    reach_through: bool = False
    expires_at: Optional[datetime] = None

class GrantResponse(BaseModel):
    id: str
    owner: str
    viewer: str
    relationship_preset: Optional[str]
    cards: CardGrants
    notify: NotifyFlags
    important: bool
    reach_through: bool
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    viewer_info: Optional[Dict[str, Any]] = None
    owner_info: Optional[Dict[str, Any]] = None

@router.put("/{viewer_id}", response_model=GrantResponse)
async def update_grant(
    viewer_id: str,
    req: GrantUpdateRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    if viewer_id == current_user_id:
        raise ValidationError("Cannot set grants for yourself")

    # Verify active connection exists
    conn = await db.connections.find_one({
        "status": ConnectionStatus.ACTIVE.value,
        "$or": [
            {"a": current_user_id, "b": viewer_id},
            {"a": viewer_id, "b": current_user_id}
        ]
    })
    if not conn:
        raise ForbiddenError("Must have an active connection before granting access")

    existing = await db.grants.find_one({"owner": current_user_id, "viewer": viewer_id})
    grant_id = str(existing["_id"]) if existing else str(ObjectId())

    grant_doc = {
        "_id": grant_id,
        "owner": current_user_id,
        "viewer": viewer_id,
        "relationship_preset": req.relationship_preset,
        "cards": req.cards.model_dump(),
        "notify": req.notify.model_dump(),
        "important": req.important,
        "reach_through": req.reach_through,
        "expires_at": req.expires_at,
        "revoked_at": None,
        "created_at": existing["created_at"] if existing else datetime.now(timezone.utc)
    }

    if existing:
        await db.grants.update_one({"_id": grant_id}, {"$set": grant_doc})
    else:
        await db.grants.insert_one(grant_doc)

    await log_audit_event(
        actor=current_user_id,
        action="GRANT_UPDATE",
        target=viewer_id,
        meta={"preset": req.relationship_preset, "cards": req.cards.model_dump()}
    )

    viewer_user = await connected_profile(db, viewer_id)
    viewer_info = {
        "id": viewer_id,
        "name": viewer_user["name"] if viewer_user else "User",
        "avatar_url": viewer_user.get("avatar_url") if viewer_user else None
    }

    return GrantResponse(
        id=grant_id,
        owner=current_user_id,
        viewer=viewer_id,
        relationship_preset=req.relationship_preset,
        cards=req.cards,
        notify=req.notify,
        important=req.important,
        reach_through=req.reach_through,
        expires_at=req.expires_at,
        revoked_at=None,
        created_at=grant_doc["created_at"],
        viewer_info=viewer_info
    )

@router.delete("/{viewer_id}")
async def revoke_grant(
    viewer_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    existing = await db.grants.find_one({"owner": current_user_id, "viewer": viewer_id})
    if not existing:
        raise NotFoundError("Grant not found")

    await db.grants.update_one(
        {"owner": current_user_id, "viewer": viewer_id},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(actor=current_user_id, action="GRANT_REVOKE", target=viewer_id)
    return {"message": "Grant revoked immediately"}

@router.get("/outgoing", response_model=List[GrantResponse])
async def list_outgoing_grants(current_user_id: str = Depends(get_current_user_id)):
    """Who can see me, and what access levels they have."""
    db = get_db()
    cursor = db.grants.find({"owner": current_user_id, "revoked_at": None})
    grants = await cursor.to_list(length=1000)

    results = []
    for g in grants:
        viewer_user = await connected_profile(db, g["viewer"])
        viewer_info = {
            "id": g["viewer"],
            "name": viewer_user["name"] if viewer_user else "User",
            "avatar_url": viewer_user.get("avatar_url") if viewer_user else None
        }
        results.append(GrantResponse(
            id=str(g["_id"]),
            owner=g["owner"],
            viewer=g["viewer"],
            relationship_preset=g.get("relationship_preset"),
            cards=CardGrants(**g.get("cards", {})),
            notify=NotifyFlags(**g.get("notify", {})),
            important=g.get("important", False),
            reach_through=g.get("reach_through", False),
            expires_at=g.get("expires_at"),
            revoked_at=g.get("revoked_at"),
            created_at=g.get("created_at", datetime.now(timezone.utc)),
            viewer_info=viewer_info
        ))
    return results

@router.get("/incoming", response_model=List[GrantResponse])
async def list_incoming_grants(current_user_id: str = Depends(get_current_user_id)):
    """Who shares with me, and what access levels I have to their context."""
    db = get_db()
    cursor = db.grants.find({"viewer": current_user_id, "revoked_at": None})
    grants = await cursor.to_list(length=1000)

    results = []
    for g in grants:
        owner_user = await connected_profile(db, g["owner"])
        owner_info = {
            "id": g["owner"],
            "name": owner_user["name"] if owner_user else "User",
            "avatar_url": owner_user.get("avatar_url") if owner_user else None
        }
        results.append(GrantResponse(
            id=str(g["_id"]),
            owner=g["owner"],
            viewer=g["viewer"],
            relationship_preset=g.get("relationship_preset"),
            cards=CardGrants(**g.get("cards", {})),
            notify=NotifyFlags(**g.get("notify", {})),
            important=g.get("important", False),
            reach_through=g.get("reach_through", False),
            expires_at=g.get("expires_at"),
            revoked_at=g.get("revoked_at"),
            created_at=g.get("created_at", datetime.now(timezone.utc)),
            owner_info=owner_info
        ))
    return results
