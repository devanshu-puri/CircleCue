"""Shared card metadata registry; cards remain configurations over existing models."""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Type

from pydantic import BaseModel

from app.domain.models import (
    Activity, ActivityMeta, ActivityType, CardKey, CheckOnMe, ExamMeta,
    ExamSet, Message, NotificationKind, PhoneState, Template, TravelMeta,
)


@dataclass(frozen=True)
class CardSpec:
    key: CardKey
    activity_types: Tuple[ActivityType, ...]
    meta_model: Optional[Any]
    defaults: Dict[str, Any]
    lifecycle: bool
    notification_kinds: Tuple[NotificationKind, ...]
    grant_card: CardKey
    collection: str
    record_model: Type[BaseModel]


CARD_REGISTRY: Dict[CardKey, CardSpec] = {
    CardKey.SCHEDULE: CardSpec(
        key=CardKey.SCHEDULE,
        activity_types=(
            ActivityType.CLASS, ActivityType.LAB, ActivityType.BREAK,
            ActivityType.LUNCH, ActivityType.FREE_PERIOD,
        ),
        meta_model=None,
        defaults={"kind": "SCHEDULE_SLOT"},
        lifecycle=False,
        notification_kinds=(NotificationKind.FREE_NOW, NotificationKind.SCHEDULE_CHANGED),
        grant_card=CardKey.SCHEDULE,
        collection="templates",
        record_model=Template,
    ),
    CardKey.EXAM: CardSpec(
        key=CardKey.EXAM,
        activity_types=(ActivityType.EXAM,),
        meta_model=ExamMeta,
        defaults={"pre_buffer_min": 30, "post_buffer_min": 15},
        lifecycle=False,
        notification_kinds=(
            NotificationKind.EXAM_STARTED, NotificationKind.EXAM_BREAK,
            NotificationKind.EXAM_FINISHED,
        ),
        grant_card=CardKey.EXAM,
        collection="exam_sets",
        record_model=ExamSet,
    ),
    CardKey.LIVE: CardSpec(
        key=CardKey.LIVE,
        activity_types=(
            ActivityType.STUDY, ActivityType.SLEEP, ActivityType.WORK,
            ActivityType.MEETING, ActivityType.MEAL, ActivityType.GYM,
            ActivityType.SOCIAL, ActivityType.FAMILY, ActivityType.BUSY,
            ActivityType.FREE, ActivityType.PERSONAL, ActivityType.CUSTOM,
        ),
        meta_model=ActivityMeta,
        defaults={"expected_duration_min": 60},
        lifecycle=True,
        notification_kinds=(
            NotificationKind.ACTIVITY_STARTED, NotificationKind.ACTIVITY_EXTENDED,
        ),
        grant_card=CardKey.LIVE,
        collection="activities",
        record_model=Activity,
    ),
    CardKey.TRAVEL: CardSpec(
        key=CardKey.TRAVEL,
        activity_types=(ActivityType.TRAVEL,),
        meta_model=TravelMeta,
        defaults={"mode": "cab", "delay_notify_min": 10},
        lifecycle=True,
        notification_kinds=(
            NotificationKind.TRAVEL_STARTED, NotificationKind.TRAVEL_DELAYED,
            NotificationKind.PLAN_CHANGED, NotificationKind.TRAVEL_ARRIVED,
        ),
        grant_card=CardKey.TRAVEL,
        collection="activities",
        record_model=Activity,
    ),
    CardKey.PHONE: CardSpec(
        key=CardKey.PHONE,
        activity_types=(ActivityType.PHONE_STATUS,),
        meta_model=PhoneState,
        defaults={"battery_low_pct": 20, "battery_critical_pct": 10, "battery_dying_pct": 5},
        lifecycle=False,
        notification_kinds=(
            NotificationKind.BATTERY_LOW, NotificationKind.BATTERY_CRITICAL,
            NotificationKind.PHONE_MAY_GO_OFFLINE,
        ),
        grant_card=CardKey.PHONE,
        collection="phone_state",
        record_model=PhoneState,
    ),
    CardKey.MESSAGE: CardSpec(
        key=CardKey.MESSAGE,
        activity_types=(),
        meta_model=Message,
        defaults={"expiry_hours": 12},
        lifecycle=False,
        notification_kinds=(NotificationKind.MESSAGE_DROP,),
        grant_card=CardKey.MESSAGE,
        collection="messages",
        record_model=Message,
    ),
    CardKey.SAFETY: CardSpec(
        key=CardKey.SAFETY,
        activity_types=(ActivityType.SAFETY,),
        meta_model=CheckOnMe,
        defaults={"grace_min": 15, "escalate_min": 15},
        lifecycle=True,
        notification_kinds=(
            NotificationKind.ARRIVAL_MISSING, NotificationKind.ALL_CLEAR,
        ),
        grant_card=CardKey.SAFETY,
        collection="activities",
        record_model=Activity,
    ),
}