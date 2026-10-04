"""Connection reminder domain logic and evaluation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import logging

from app.domain.models import NotificationKind
from app.domain.notifications import notification_broker

logger = logging.getLogger("circlecue.reminders")


def _rule_to_seconds(rule: str, cooldown_min: int = 1440) -> float:
    rule_lower = rule.strip().lower()
    if rule_lower == "daily":
        return 86400.0
    elif rule_lower == "weekly":
        return 7 * 86400.0
    elif rule_lower == "biweekly":
        return 14 * 86400.0
    elif rule_lower == "monthly":
        return 30 * 86400.0
    try:
        days = float(rule_lower)
        return days * 86400.0
    except ValueError:
        return cooldown_min * 60.0


async def evaluate_connection_reminders(
    db: Any,
    owner_id: str,
    now: datetime,
) -> List[Dict[str, Any]]:
    """Evaluate connection plans for owner and trigger connection reminders."""
    plans = await db.connection_plans.find({"owner": owner_id}).to_list(length=100)
    created_notifications: List[Dict[str, Any]] = []

    for plan in plans:
        # Check importance
        if plan.get("importance") != "high":
            continue

        # Check daily nudge cap (max 2 nudges per day)
        nudges_today = plan.get("nudges_today", 0)
        last_nudge_at = plan.get("last_nudge_at")
        if last_nudge_at:
            if isinstance(last_nudge_at, str):
                last_nudge_dt = datetime.fromisoformat(last_nudge_at)
            else:
                last_nudge_dt = last_nudge_at
            # Reset daily count if last nudge was on a different day (UTC)
            if last_nudge_dt.date() < now.date():
                nudges_today = 0
                await db.connection_plans.update_one(
                    {"_id": plan["_id"]},
                    {"$set": {"nudges_today": 0}},
                )
            elif (now - last_nudge_dt).total_seconds() < 14400:
                continue

        if nudges_today >= 2:
            continue

        # Check snooze
        snoozed_until = plan.get("snoozed_until")
        if snoozed_until:
            if isinstance(snoozed_until, str):
                snooze_dt = datetime.fromisoformat(snoozed_until)
            else:
                snooze_dt = snoozed_until
            if now < snooze_dt:
                continue

        # Check cadence
        rule = plan.get("rule", "weekly")
        cooldown_min = plan.get("cooldown_min", 1440)
        interval_sec = _rule_to_seconds(rule, cooldown_min)

        last_conn = plan.get("last_connected_at")
        due = False
        if last_conn is None:
            due = True
        else:
            if isinstance(last_conn, str):
                last_conn_dt = datetime.fromisoformat(last_conn)
            else:
                last_conn_dt = last_conn
            if (now - last_conn_dt).total_seconds() >= interval_sec:
                due = True

        if not due:
            continue

        # Target info for text
        target_id = plan.get("target", "Friend")
        target_user = await db.users.find_one({"_id": target_id})
        target_name = target_user.get("name", "your friend") if target_user else "your friend"

        today_str = now.strftime("%Y-%m-%d")
        dedupe_key = f"connection-reminder:{plan['_id']}:{today_str}:{nudges_today}"

        # Dedupe check
        if await db.notifications.find_one({"_id": dedupe_key}):
            continue

        notification_doc = {
            "_id": dedupe_key,
            "to": owner_id,
            "about_owner": owner_id,
            "kind": NotificationKind.CONNECTION_REMINDER.value,
            "payload_redacted": {
                "text": f"It's been a while since you connected with {target_name}. Want to reach out?",
                "target_id": target_id,
                "target_name": target_name,
                "plan_id": str(plan["_id"]),
            },
            "action": "CALL",
            "dedupe_key": dedupe_key,
            "status": "pending",
            "owner_only": True,
            "created_at": now,
        }

        await db.notifications.insert_one(notification_doc)
        notification_broker.publish(owner_id, notification_doc)
        created_notifications.append(notification_doc)

        # Increment nudges_today and update last_nudge_at
        await db.connection_plans.update_one(
            {"_id": plan["_id"]},
            {
                "$set": {
                    "nudges_today": nudges_today + 1,
                    "last_nudge_at": now,
                }
            },
        )

    return created_notifications
