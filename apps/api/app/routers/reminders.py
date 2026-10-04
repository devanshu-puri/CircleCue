"""Reminders and predictor router."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.clock import Clock, get_clock
from app.core.security import get_current_user_id
from app.db import get_db
from app.domain.models import ConnectionPlan
from app.domain.reminders import evaluate_connection_reminders
from app.predict.pickup import predict_pickup_probability

router = APIRouter(tags=["reminders"])


class CreatePlanRequest(BaseModel):
    target: str
    importance: str = Field(default="normal", pattern="^(low|normal|high)$")
    rule: str = Field(default="weekly") # daily, weekly, biweekly, monthly, or number of days
    preferred_window: Optional[Dict[str, str]] = None
    cooldown_min: int = 1440


class SnoozeRequest(BaseModel):
    days: Optional[int] = 3
    until: Optional[datetime] = None


class PredictPickupRequest(BaseModel):
    reachability_calls: str = "ok" # ok, prefer_not, no
    battery_bucket: str = "ok" # ok, low, critical, dying
    phone_mode: str = "normal" # normal, silent, dnd
    declared_offline: bool = False
    may_go_offline: bool = False
    local_hour: int = 12


@router.get("/reminders/plans")
async def list_plans(
    current_user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db),
) -> List[Dict[str, Any]]:
    plans = await db.connection_plans.find({"owner": current_user_id}).to_list(length=100)
    for p in plans:
        p["_id"] = str(p["_id"])
    return plans


@router.post("/reminders/plans", status_code=status.HTTP_201_CREATED)
async def create_plan(
    req: CreatePlanRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Dict[str, Any]:
    plan_id = str(uuid4())
    doc = {
        "_id": plan_id,
        "owner": current_user_id,
        "target": req.target,
        "importance": req.importance,
        "rule": req.rule,
        "preferred_window": req.preferred_window,
        "last_connected_at": None,
        "snoozed_until": None,
        "cooldown_min": req.cooldown_min,
        "nudges_today": 0,
        "created_at": clock.now(),
    }
    await db.connection_plans.insert_one(doc)
    return doc


@router.post("/reminders/plans/{plan_id}/snooze")
async def snooze_plan(
    plan_id: str,
    req: SnoozeRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Dict[str, Any]:
    now = clock.now()
    if req.until:
        snooze_until = req.until
    else:
        days = req.days or 3
        snooze_until = now + timedelta(days=days)

    res = await db.connection_plans.update_one(
        {"_id": plan_id, "owner": current_user_id},
        {"$set": {"snoozed_until": snooze_until}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Connection plan not found")
    return {"status": "snoozed", "snoozed_until": snooze_until.isoformat()}


@router.post("/reminders/plans/{plan_id}/connected")
async def mark_connected(
    plan_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Dict[str, Any]:
    now = clock.now()
    res = await db.connection_plans.update_one(
        {"_id": plan_id, "owner": current_user_id},
        {"$set": {"last_connected_at": now, "nudges_today": 0}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Connection plan not found")
    return {"status": "connected", "last_connected_at": now.isoformat()}


@router.post("/reminders/check")
async def check_reminders(
    current_user_id: str = Depends(get_current_user_id),
    db: Any = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Dict[str, Any]:
    now = clock.now()
    notifications = await evaluate_connection_reminders(db, current_user_id, now)
    return {"evaluated_count": len(notifications), "notifications": notifications}


@router.post("/predict/pickup")
async def predict_pickup(
    req: PredictPickupRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    prob = predict_pickup_probability(req.model_dump())
    return {"probability": prob, "features": req.model_dump()}
