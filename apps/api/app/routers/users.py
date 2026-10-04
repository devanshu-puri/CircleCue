import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.db import get_db
from app.core.security import get_current_user_id, generate_user_code
from app.core.errors import NotFoundError, ValidationError
from app.core.ratelimit import code_lookup_limiter
from app.core.audit import log_audit_event
from app.domain.models import User, RoutinePrefs, AIPrefs, SharingPaused
from app.domain.visibility import profile_by_code

router = APIRouter(tags=["users"])

class UserProfileResponse(BaseModel):
    id: str
    name: str
    user_code: str
    email: str
    tz: str
    avatar_url: Optional[str] = None
    routine_prefs: RoutinePrefs
    ai_prefs: AIPrefs
    sharing_paused: SharingPaused
    created_at: datetime

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    tz: Optional[str] = Field(default=None, max_length=50)
    routine_prefs: Optional[RoutinePrefs] = None
    ai_prefs: Optional[AIPrefs] = None

class CodeLookupResponse(BaseModel):
    user_code: str
    name: str
    avatar_url: Optional[str] = None

class PauseRequest(BaseModel):
    until: Optional[datetime] = None

class RoutineRequest(BaseModel):
    wake: str = "07:00"
    sleep: str = "23:00"
    min_call_window_min: int = 10
    buffer_min: int = 5

@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"_id": current_user_id})
    if not user:
        raise NotFoundError("User profile not found")

    return UserProfileResponse(
        id=str(user["_id"]),
        name=user["name"],
        user_code=user["user_code"],
        email=user["email"],
        tz=user.get("tz", "UTC"),
        avatar_url=user.get("avatar_url"),
        routine_prefs=RoutinePrefs(**user.get("routine_prefs", {})),
        ai_prefs=AIPrefs(**user.get("ai_prefs", {})),
        sharing_paused=SharingPaused(**user.get("sharing_paused", {})),
        created_at=user.get("created_at", datetime.now(timezone.utc))
    )

@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    req: UpdateProfileRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    updates: Dict[str, Any] = {}
    
    if req.name is not None:
        updates["name"] = req.name.strip()
    if req.avatar_url is not None:
        updates["avatar_url"] = req.avatar_url.strip()
    if req.tz is not None:
        updates["tz"] = req.tz.strip()
    if req.routine_prefs is not None:
        updates["routine_prefs"] = req.routine_prefs.model_dump()
    if req.ai_prefs is not None:
        updates["ai_prefs"] = req.ai_prefs.model_dump()

    if updates:
        await db.users.update_one({"_id": current_user_id}, {"$set": updates})

    return await get_me(current_user_id=current_user_id)

@router.post("/me/code/rotate")
async def rotate_code(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"_id": current_user_id})
    if not user:
        raise NotFoundError("User not found")

    new_code = generate_user_code(user["name"])
    for _ in range(5):
        if not await db.users.find_one({"user_code": new_code}):
            break
        new_code = generate_user_code(user["name"])

    await db.users.update_one({"_id": current_user_id}, {"$set": {"user_code": new_code}})
    await log_audit_event(actor=current_user_id, action="CODE_ROTATE", meta={"new_code": new_code})

    return {"user_code": new_code}

@router.get("/users/code-lookup", response_model=CodeLookupResponse)
async def lookup_code(code: str, request: Request):
    # Rate limit check per IP/user
    client_ip = request.client.host if request.client else "unknown"
    code_lookup_limiter.check(client_ip)

    clean_code = code.strip().upper()
    db = get_db()
    user = await profile_by_code(db, clean_code)

    # Constant time behavior for privacy
    if not user:
        await asyncio.sleep(0.05)
        raise NotFoundError("User code not found")

    return CodeLookupResponse(
        user_code=user["user_code"],
        name=user["name"].split()[0], # Only first name returned for privacy
        avatar_url=user.get("avatar_url")
    )

@router.put("/me/routine")
async def set_routine(
    req: RoutineRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    routine_prefs = RoutinePrefs(
        wake=req.wake,
        sleep=req.sleep,
        min_call_window_min=req.min_call_window_min,
        buffer_min=req.buffer_min
    )
    
    await db.users.update_one(
        {"_id": current_user_id},
        {"$set": {"routine_prefs": routine_prefs.model_dump()}}
    )
    
    await log_audit_event(actor=current_user_id, action="ROUTINE_UPDATE", meta=routine_prefs.model_dump())
    return {"message": "Routine updated successfully", "routine_prefs": routine_prefs.model_dump()}

@router.post("/me/pause")
async def pause_sharing(
    req: Optional[PauseRequest] = None,
    current_user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    until = req.until if req else None
    pause_state = SharingPaused(active=True, until=until)
    await db.users.update_one(
        {"_id": current_user_id},
        {"$set": {"sharing_paused": pause_state.model_dump()}}
    )
    await log_audit_event(actor=current_user_id, action="SHARING_PAUSE", meta={"until": until.isoformat() if until else None})
    return {"sharing_paused": pause_state.model_dump()}

@router.delete("/me/pause")
async def unpause_sharing(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    pause_state = SharingPaused(active=False, until=None)
    await db.users.update_one(
        {"_id": current_user_id},
        {"$set": {"sharing_paused": pause_state.model_dump()}}
    )
    await log_audit_event(actor=current_user_id, action="SHARING_UNPAUSE")
    return {"sharing_paused": pause_state.model_dump()}

@router.get("/me/export")
async def export_my_data(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"_id": current_user_id})
    if not user:
        raise NotFoundError("User not found")
        
    user.pop("pw_hash", None)
    
    activities = await db.activities.find({"owner": current_user_id}).to_list(length=1000)
    templates = await db.templates.find({"owner": current_user_id}).to_list(length=1000)
    grants = await db.grants.find({"owner": current_user_id}).to_list(length=1000)
    connections = await db.connections.find({"$or": [{"a": current_user_id}, {"b": current_user_id}]}).to_list(length=1000)
    scenarios = await db.scenarios.find({"owner": current_user_id}).to_list(length=1000)
    messages = await db.messages.find({"owner": current_user_id}).to_list(length=1000)
    
    return {
        "user": user,
        "activities": activities,
        "templates": templates,
        "grants": grants,
        "connections": connections,
        "scenarios": scenarios,
        "messages": messages,
        "exported_at": datetime.now(timezone.utc).isoformat()
    }

@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_account(current_user_id: str = Depends(get_current_user_id)):
    db = get_db()
    # Purge owned records
    await db.users.delete_one({"_id": current_user_id})
    await db.activities.delete_many({"owner": current_user_id})
    await db.templates.delete_many({"owner": current_user_id})
    await db.grants.delete_many({"$or": [{"owner": current_user_id}, {"viewer": current_user_id}]})
    await db.connections.delete_many({"$or": [{"a": current_user_id}, {"b": current_user_id}]})
    await db.scenarios.delete_many({"owner": current_user_id})
    await db.messages.delete_many({"owner": current_user_id})
    await db.phone_state.delete_one({"_id": current_user_id})

    try:
        from app.workflows.client import terminate_user_workflows
        await terminate_user_workflows(current_user_id)
    except Exception:
        pass

    await log_audit_event(actor=current_user_id, action="ACCOUNT_DELETE")
    return {"message": "Account and associated data deleted permanently."}
