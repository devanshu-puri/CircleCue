from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Response, Request, Depends, status
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId

from app.db import get_db
from app.domain.models import User, RoutinePrefs, AIPrefs, SharingPaused
from app.core.security import hash_password, verify_password, create_access_token, generate_user_code
from app.core.errors import CircleCueError, ValidationError, UnauthorizedError
from app.core.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    tz: Optional[str] = "UTC"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    id: str
    name: str
    email: str
    user_code: str
    tz: str
    token: Optional[str] = None
    read_only: bool = False

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, response: Response, request: Request):
    db = get_db()
    email_clean = req.email.strip().lower()
    
    # Check existing email
    existing_user = await db.users.find_one({"email": email_clean})
    if existing_user:
        raise ValidationError(message="Email already registered")

    # Generate unique user_code with collision retries
    user_code = generate_user_code(req.name)
    for _ in range(5):
        if not await db.users.find_one({"user_code": user_code}):
            break
        user_code = generate_user_code(req.name)

    pw_hash = hash_password(req.password)
    new_id = str(ObjectId())

    user_doc = {
        "_id": new_id,
        "name": req.name.strip(),
        "user_code": user_code,
        "email": email_clean,
        "pw_hash": pw_hash,
        "tz": req.tz or "UTC",
        "avatar_url": None,
        "routine_prefs": RoutinePrefs().model_dump(),
        "ai_prefs": AIPrefs().model_dump(),
        "sharing_paused": SharingPaused().model_dump(),
        "created_at": datetime.now(timezone.utc)
    }

    await db.users.insert_one(user_doc)
    
    # Set JWT in httpOnly cookie
    token = create_access_token(new_id)
    is_https = request.url.scheme == "https"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https,
        samesite="none" if is_https else "lax",
        max_age=604800
    )

    await log_audit_event(actor=new_id, action="USER_REGISTER", target=new_id)

    from app.config import settings
    if settings.TEMPORAL_ENABLED:
        try:
            from app.workflows.client import ensure_timeline
            await ensure_timeline(new_id)
        except Exception:
            try:
                await db.users.update_one({"_id": new_id}, {"$set": {"needs_resync": True}})
            except Exception:
                pass

    return AuthResponse(
        id=new_id,
        name=req.name.strip(),
        email=email_clean,
        user_code=user_code,
        tz=req.tz or "UTC",
        token=token
    )

@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, response: Response, request: Request):
    db = get_db()
    email_clean = req.email.strip().lower()
    
    user = await db.users.find_one({"email": email_clean})
    if not user or not verify_password(req.password, user["pw_hash"]):
        await log_audit_event(actor="anonymous", action="LOGIN_FAILED", meta={"email": email_clean})
        raise UnauthorizedError("Invalid email or password")

    user_id = str(user["_id"])
    token = create_access_token(user_id)
    
    is_https = request.url.scheme == "https"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https,
        samesite="none" if is_https else "lax",
        max_age=604800
    )

    await log_audit_event(actor=user_id, action="USER_LOGIN", target=user_id)

    return AuthResponse(
        id=user_id,
        name=user["name"],
        email=user["email"],
        user_code=user["user_code"],
        tz=user.get("tz", "UTC"),
        token=token
    )


@router.post(
    "/demo",
    response_model=AuthResponse,
    summary="Start a read-only demo session",
    description="Signs into the configured public demo account. Mutating API requests are rejected for this session.",
)
async def demo_login(response: Response, request: Request):
    from app.config import settings

    if not settings.DEMO_USER_EMAIL:
        raise ValidationError(message="The demo is not available right now")

    db = get_db()
    user = await db.users.find_one({"email": settings.DEMO_USER_EMAIL.strip().lower()})
    if not user:
        raise ValidationError(message="The demo account is not set up yet")

    user_id = str(user["_id"])
    token = create_access_token(user_id, read_only_demo=True)
    is_https = request.url.scheme == "https"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https,
        samesite="none" if is_https else "lax",
        max_age=604800,
    )
    await log_audit_event(actor=user_id, action="DEMO_LOGIN", target=user_id)
    return AuthResponse(
        id=user_id,
        name=user["name"],
        email=user["email"],
        user_code=user["user_code"],
        tz=user.get("tz", "UTC"),
        token=token,
        read_only=True,
    )

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}
