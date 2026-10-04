from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import get_db
from app.core.security import get_current_user_id
from app.core.errors import NotFoundError, ValidationError, ForbiddenError
from app.core.audit import log_audit_event
from app.domain.models import ConnectionStatus
from app.domain.visibility import connected_profile, profile_by_code

router = APIRouter(prefix="/connections", tags=["connections"])

class RequestConnectionPayload(BaseModel):
    user_code: str = Field(..., max_length=20)

class ConnectionResponse(BaseModel):
    id: str
    a: str
    b: str
    status: ConnectionStatus
    requested_by: str
    target_user: Dict[str, Any]
    created_at: datetime

@router.post("/request", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def request_connection(
    req: RequestConnectionPayload,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    code_clean = req.user_code.strip().upper()
    
    target_user = await profile_by_code(db, code_clean)
    if not target_user:
        raise NotFoundError("User code not found")
        
    target_id = target_user["id"]
    if target_id == current_user_id:
        raise ValidationError("Cannot connect with yourself")

    # Check existing connection between A and B
    existing = await db.connections.find_one({
        "$or": [
            {"a": current_user_id, "b": target_id},
            {"a": target_id, "b": current_user_id}
        ]
    })
    
    if existing:
        if existing["status"] == ConnectionStatus.BLOCKED.value:
            raise ForbiddenError("Connection blocked")
        if existing["status"] == ConnectionStatus.ACTIVE.value:
            raise ValidationError("Already connected")
        if existing["status"] == ConnectionStatus.PENDING.value:
            # Return existing pending connection
            return ConnectionResponse(
                id=str(existing["_id"]),
                a=existing["a"],
                b=existing["b"],
                status=ConnectionStatus(existing["status"]),
                requested_by=existing["requested_by"],
                target_user={"id": target_id, "name": target_user["name"], "avatar_url": target_user.get("avatar_url")},
                created_at=existing["created_at"]
            )

    new_id = str(ObjectId())
    conn_doc = {
        "_id": new_id,
        "a": current_user_id,
        "b": target_id,
        "status": ConnectionStatus.PENDING.value,
        "requested_by": current_user_id,
        "created_at": datetime.now(timezone.utc)
    }

    await db.connections.insert_one(conn_doc)
    await log_audit_event(actor=current_user_id, action="CONNECTION_REQUEST", target=target_id)

    return ConnectionResponse(
        id=new_id,
        a=current_user_id,
        b=target_id,
        status=ConnectionStatus.PENDING,
        requested_by=current_user_id,
        target_user={"id": target_id, "name": target_user["name"], "avatar_url": target_user.get("avatar_url")},
        created_at=conn_doc["created_at"]
    )

@router.post("/{connection_id}/accept", response_model=ConnectionResponse)
async def accept_connection(
    connection_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    conn = await db.connections.find_one({"_id": connection_id})
    if not conn:
        raise NotFoundError("Connection request not found")

    if conn["b"] != current_user_id:
        raise ForbiddenError("Only the recipient can accept a connection request")

    await db.connections.update_one(
        {"_id": connection_id},
        {"$set": {"status": ConnectionStatus.ACTIVE.value}}
    )
    
    await log_audit_event(actor=current_user_id, action="CONNECTION_ACCEPT", target=conn["a"])

    other_id = conn["a"]
    other_user = await connected_profile(db, other_id)

    return ConnectionResponse(
        id=connection_id,
        a=conn["a"],
        b=conn["b"],
        status=ConnectionStatus.ACTIVE,
        requested_by=conn["requested_by"],
        target_user={"id": other_id, "name": other_user["name"] if other_user else "User", "avatar_url": other_user.get("avatar_url") if other_user else None},
        created_at=conn["created_at"]
    )

@router.post("/{connection_id}/decline")
async def decline_connection(
    connection_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    conn = await db.connections.find_one({"_id": connection_id})
    if not conn:
        raise NotFoundError("Connection request not found")

    if conn["b"] != current_user_id and conn["a"] != current_user_id:
        raise ForbiddenError("Not authorized")

    await db.connections.delete_one({"_id": connection_id})
    await log_audit_event(actor=current_user_id, action="CONNECTION_DECLINE", target=conn["a"] if conn["b"] == current_user_id else conn["b"])
    return {"message": "Connection request declined"}

@router.post("/{connection_id}/block")
async def block_connection(
    connection_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    conn = await db.connections.find_one({"_id": connection_id})
    if not conn:
        raise NotFoundError("Connection not found")

    if conn["a"] != current_user_id and conn["b"] != current_user_id:
        raise ForbiddenError("Not authorized")

    other_id = conn["b"] if conn["a"] == current_user_id else conn["a"]

    # Set connection to blocked
    await db.connections.update_one(
        {"_id": connection_id},
        {"$set": {"status": ConnectionStatus.BLOCKED.value}}
    )

    # Immediate Revocation: delete all grants between both users in both directions
    await db.grants.update_many(
        {
            "$or": [
                {"owner": current_user_id, "viewer": other_id},
                {"owner": other_id, "viewer": current_user_id}
            ]
        },
        {"$set": {"revoked_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(actor=current_user_id, action="CONNECTION_BLOCK", target=other_id)
    return {"message": "User blocked and all mutual access revoked"}

@router.delete("/{connection_id}")
async def remove_connection(
    connection_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    conn = await db.connections.find_one({"_id": connection_id})
    if not conn:
        raise NotFoundError("Connection not found")

    if conn["a"] != current_user_id and conn["b"] != current_user_id:
        raise ForbiddenError("Not authorized")

    other_id = conn["b"] if conn["a"] == current_user_id else conn["a"]

    await db.connections.delete_one({"_id": connection_id})
    
    # Immediately revoke all grants in both directions
    await db.grants.update_many(
        {
            "$or": [
                {"owner": current_user_id, "viewer": other_id},
                {"owner": other_id, "viewer": current_user_id}
            ]
        },
        {"$set": {"revoked_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(actor=current_user_id, action="CONNECTION_REMOVE", target=other_id)
    return {"message": "Connection removed"}

@router.get("", response_model=List[ConnectionResponse])
async def list_connections(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.connections.find({
        "$or": [{"a": current_user_id}, {"b": current_user_id}]
    })
    conns = await cursor.to_list(length=1000)

    results = []
    for conn in conns:
        other_id = conn["b"] if conn["a"] == current_user_id else conn["a"]
        other_user = await connected_profile(db, other_id)
        target_info = {
            "id": other_id,
            "name": other_user["name"] if other_user else "User",
            "avatar_url": other_user.get("avatar_url") if other_user else None
        }
        results.append(ConnectionResponse(
            id=str(conn["_id"]),
            a=conn["a"],
            b=conn["b"],
            status=ConnectionStatus(conn["status"]),
            requested_by=conn["requested_by"],
            target_user=target_info,
            created_at=conn["created_at"]
        ))
    return results
