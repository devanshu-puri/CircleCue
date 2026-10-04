from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator
import html
import re

# --- ENUMS ---

class ActivityType(str, Enum):
    CLASS = "CLASS"
    LAB = "LAB"
    BREAK = "BREAK"
    LUNCH = "LUNCH"
    FREE_PERIOD = "FREE_PERIOD"
    EXAM = "EXAM"
    STUDY = "STUDY"
    SLEEP = "SLEEP"
    WORK = "WORK"
    MEETING = "MEETING"
    TRAVEL = "TRAVEL"
    MEAL = "MEAL"
    GYM = "GYM"
    SOCIAL = "SOCIAL"
    FAMILY = "FAMILY"
    BUSY = "BUSY"
    FREE = "FREE"
    PERSONAL = "PERSONAL"
    PHONE_STATUS = "PHONE_STATUS"
    SAFETY = "SAFETY"
    CUSTOM = "CUSTOM"

class Status(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    EXTENDED = "EXTENDED"
    DELAYED = "DELAYED"
    CHANGED = "CHANGED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class TravelPhase(str, Enum):
    PLANNED = "planned"
    TRAVELLING = "travelling"
    DELAYED = "delayed"
    ARRIVED = "arrived"
    COMPLETED = "completed"

class CardKey(str, Enum):
    SCHEDULE = "schedule"
    EXAM = "exam"
    LIVE = "live"
    TRAVEL = "travel"
    PHONE = "phone"
    SAFETY = "safety"
    MESSAGE = "message"

class AccessLevel(str, Enum):
    NONE = "none"
    STATUS = "status"
    DETAILS = "details"

class Calls(str, Enum):
    OK = "ok"
    PREFER_NOT = "prefer_not"
    NO = "no"

class Messages(str, Enum):
    OK = "ok"
    LATER = "later"

class ProvenanceSource(str, Enum):
    USER_SHARED = "user_shared"
    AI_PARSED_USER_CONFIRMED = "ai_parsed_user_confirmed"
    SYSTEM_INFERRED = "system_inferred"
    SYSTEM_COLLECTED = "system_collected"

class NotificationKind(str, Enum):
    FREE_NOW = "FREE_NOW"
    EXAM_STARTED = "EXAM_STARTED"
    EXAM_BREAK = "EXAM_BREAK"
    EXAM_FINISHED = "EXAM_FINISHED"
    CLASS_CANCELLED = "CLASS_CANCELLED"
    SCHEDULE_CHANGED = "SCHEDULE_CHANGED"
    ACTIVITY_STARTED = "ACTIVITY_STARTED"
    ACTIVITY_EXTENDED = "ACTIVITY_EXTENDED"
    EXAM_SET_CHANGED = "EXAM_SET_CHANGED"
    PHONE_STATE_CHANGED = "PHONE_STATE_CHANGED"
    SAFETY_WATCH_STARTED = "SAFETY_WATCH_STARTED"
    TRAVEL_STARTED = "TRAVEL_STARTED"
    TRAVEL_DELAYED = "TRAVEL_DELAYED"
    PLAN_CHANGED = "PLAN_CHANGED"
    TRAVEL_ARRIVED = "TRAVEL_ARRIVED"
    BATTERY_LOW = "BATTERY_LOW"
    BATTERY_CRITICAL = "BATTERY_CRITICAL"
    PHONE_MAY_GO_OFFLINE = "PHONE_MAY_GO_OFFLINE"
    MESSAGE_DROP = "MESSAGE_DROP"
    ARRIVAL_MISSING = "ARRIVAL_MISSING"
    ALL_CLEAR = "ALL_CLEAR"
    PROMISE_DUE = "PROMISE_DUE"
    URGENT_OVERRIDE = "URGENT_OVERRIDE"
    CONNECTION_REMINDER = "CONNECTION_REMINDER"

class ConnectionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"

class ExceptionKind(str, Enum):
    CANCELLED = "cancelled"
    MOVED = "moved"
    EXTENDED = "extended"
    EARLY_END = "early_end"
    DAY_OFF = "day_off"

class TemplateKind(str, Enum):
    SCHEDULE_SLOT = "SCHEDULE_SLOT"
    ROUTINE = "ROUTINE"
    SCENARIO_TIME = "SCENARIO_TIME"

class WeekPattern(str, Enum):
    EVERY = "every"
    A = "A"
    B = "B"

# --- HELPER / SUB-MODELS ---

def sanitize_text(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    # Store readable plain text; API data is rendered as text by React, which
    # escapes markup at the output boundary. Decode legacy entities first.
    cleaned = html.unescape(v.strip())
    cleaned = re.sub(r"<[^>]*>", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    return cleaned

class Provenance(BaseModel):
    source: ProvenanceSource
    model: Optional[str] = None
    confidence: Optional[float] = None
    confirmed_at: Optional[datetime] = None

class RoutinePrefs(BaseModel):
    wake: str = "07:00"
    sleep: str = "23:00"
    min_call_window_min: int = 10
    buffer_min: int = 5

class AIPrefs(BaseModel):
    store_raw: bool = False

class SharingPaused(BaseModel):
    active: bool = False
    until: Optional[datetime] = None

class Availability(BaseModel):
    calls: Calls = Calls.OK
    messages: Messages = Messages.OK
    reason: Optional[str] = Field(default=None, max_length=100)

class CardGrants(BaseModel):
    schedule: AccessLevel = AccessLevel.NONE
    exam: AccessLevel = AccessLevel.NONE
    live: AccessLevel = AccessLevel.NONE
    travel: AccessLevel = AccessLevel.NONE
    phone: AccessLevel = AccessLevel.NONE
    safety: AccessLevel = AccessLevel.NONE
    message: AccessLevel = AccessLevel.NONE

class NotifyFlags(BaseModel):
    free_now: bool = False
    activity: bool = False
    phone: bool = False
    exam: bool = False
    travel: bool = False
    battery: bool = False
    schedule_change: bool = False
    message: bool = False
    safety: bool = True

class CheckOnMe(BaseModel):
    enabled: bool = False
    grace_min: int = 15
    escalate_min: int = 15

class VisibilitySpec(BaseModel):
    mode: Literal["inherit", "private_label", "only"] = "inherit"
    label_override: Optional[str] = Field(default=None, max_length=50)
    viewer_ids: List[str] = Field(default_factory=list)

# Metadata Models (Discriminated Union support)
class TravelMeta(BaseModel):
    kind: Literal["travel"] = "travel"
    destination: str = Field(..., max_length=100)
    destination_kind: Optional[str] = Field(default="other", max_length=30)
    depart: Optional[str] = None
    eta: Optional[datetime] = None
    mode: str = Field(default="cab", max_length=30)
    companions: List[str] = Field(default_factory=list)
    companion_phone: Optional[str] = Field(default=None, max_length=20)
    expected_return_at: Optional[datetime] = None
    vehicle_number: Optional[str] = Field(default=None, max_length=30)
    driver_name: Optional[str] = Field(default=None, max_length=50)
    driver_phone: Optional[str] = Field(default=None, max_length=20)
    route_number: Optional[str] = Field(default=None, max_length=30)
    expected_offline_window: Optional[Dict[str, datetime]] = None

class ExamItem(BaseModel):
    type: Literal["exam", "break"]
    subject: Optional[str] = Field(default=None, max_length=50)
    start_local: str
    end_local: str
    calls_ok: bool = False

class ExamMeta(BaseModel):
    kind: Literal["exam"] = "exam"
    subject: str = Field(..., max_length=50)
    state: str = Field(default="upcoming", max_length=30)
    exams_today: int = 1
    items: List[ExamItem] = Field(default_factory=list)

class StudyMeta(BaseModel):
    kind: Literal["study"] = "study"
    subject: Optional[str] = Field(default=None, max_length=50)

class SleepMeta(BaseModel):
    kind: Literal["sleep"] = "sleep"
    wake_alarm: Optional[str] = None

class CustomMeta(BaseModel):
    kind: Literal["custom"] = "custom"
    icon: Optional[str] = Field(default=None, max_length=30)
    label: Optional[str] = Field(default=None, max_length=50)
    extra: Dict[str, str] = Field(default_factory=dict)

ActivityMeta = Union[TravelMeta, ExamMeta, StudyMeta, SleepMeta, CustomMeta]

# --- MAIN COLLECTION MODELS ---

class User(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    name: str = Field(..., max_length=100)
    user_code: str = Field(..., max_length=20)
    email: EmailStr
    pw_hash: str
    tz: str = "UTC"
    avatar_url: Optional[str] = None
    current_place: Optional[str] = Field(default=None, max_length=100)
    routine_prefs: RoutinePrefs = Field(default_factory=RoutinePrefs)
    ai_prefs: AIPrefs = Field(default_factory=AIPrefs)
    sharing_paused: SharingPaused = Field(default_factory=SharingPaused)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        return sanitize_text(v) or v

class Connection(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    a: str
    b: str
    status: ConnectionStatus = ConnectionStatus.PENDING
    requested_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Grant(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    viewer: str
    relationship_preset: Optional[str] = Field(default="friend", max_length=30)
    cards: CardGrants = Field(default_factory=CardGrants)
    notify: NotifyFlags = Field(default_factory=NotifyFlags)
    important: bool = False
    reach_through: bool = False
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ShareLink(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    code: str
    owner: str
    scope: Dict[str, Any]
    expires_at: datetime
    max_uses: int = 1
    uses: int = 0
    revoked_at: Optional[datetime] = None

class Template(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    kind: TemplateKind
    title: str = Field(..., max_length=100)
    activity_type: ActivityType
    days: List[int] = Field(default_factory=list) # 0=Monday, 6=Sunday
    start_local: str # "09:00"
    end_local: str # "10:00"
    week_pattern: WeekPattern = WeekPattern.EVERY
    availability: Availability = Field(default_factory=Availability)
    visibility: VisibilitySpec = Field(default_factory=VisibilitySpec)
    active_from: Optional[datetime] = None
    active_to: Optional[datetime] = None
    version: int = 1

    @field_validator("title")
    def validate_title(cls, v: str) -> str:
        return sanitize_text(v) or v

class ExceptionItem(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    template_id: Optional[str] = None
    date: str # "YYYY-MM-DD"
    kind: ExceptionKind
    new_start: Optional[str] = None
    new_end: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=200)
    version: int = 1

class ExamSet(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    date: str # "YYYY-MM-DD"
    items: List[ExamItem] = Field(default_factory=list)
    pre_buffer_min: int = 30
    post_buffer_min: int = 15
    keep_schedule: bool = False
    version: int = 1

class Activity(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    type: ActivityType
    title: str = Field(..., max_length=100)
    status: Status = Status.ACTIVE
    phase: Optional[TravelPhase] = None
    start_at: datetime
    expected_end_at: datetime
    availability: Availability = Field(default_factory=Availability)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    visibility: VisibilitySpec = Field(default_factory=VisibilitySpec)
    participants: List[str] = Field(default_factory=list)
    provenance: Provenance
    check_on_me: Optional[CheckOnMe] = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title")
    def validate_title(cls, v: str) -> str:
        return sanitize_text(v) or v

class ContextSnapshot(BaseModel):
    snapshot: Dict[str, Any]
    shared_at: datetime

class PhoneState(BaseModel):
    owner: str = Field(..., alias="_id")
    mode: str = "normal"
    calls: Calls = Calls.OK
    messages: Messages = Messages.OK
    battery_pct: int = 100
    battery_bucket: str = "ok" # ok, low, critical, dying
    may_go_offline: bool = False
    declared_offline: bool = False
    until: Optional[datetime] = None
    last_shared_context: Optional[ContextSnapshot] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

class Message(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    text: str = Field(..., max_length=280)
    template_key: Optional[str] = None
    activity_id: Optional[str] = None
    audience: List[str] = Field(default_factory=list)
    expires_at: datetime
    promise_at: Optional[datetime] = None
    promise_done_at: Optional[datetime] = None
    reactions: List[Dict[str, str]] = Field(default_factory=list)
    version: int = 1

    @field_validator("text")
    def validate_text(cls, v: str) -> str:
        return sanitize_text(v) or v

class Scenario(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    name: str = Field(..., max_length=100)
    enabled: bool = True
    source: Dict[str, Any] = Field(default_factory=dict)
    trigger: Dict[str, Any] = Field(default_factory=dict)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    effects: List[Dict[str, Any]] = Field(default_factory=list)
    audience: List[str] = Field(default_factory=list)
    audience_mode: Literal["all_granted", "only", "except"] = "all_granted"
    notification_rule: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 50
    last_fired_at: Optional[datetime] = None
    version: int = 1

class ConnectionPlan(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    owner: str
    target: str
    importance: str = "normal"
    rule: str = "weekly"
    preferred_window: Optional[Dict[str, str]] = None
    last_connected_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    cooldown_min: int = 1440
    nudges_today: int = 0

class CallEvent(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    caller: str
    callee: str
    ts: datetime
    outcome: Literal["picked", "missed"]
    features: Dict[str, Any] = Field(default_factory=dict)
    synthetic: bool = False

class Notification(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    to: str
    about_owner: str
    kind: NotificationKind
    payload_redacted: Dict[str, Any]
    action: Optional[str] = None # CALL, MESSAGE, REMIND_LATER, NONE
    dedupe_key: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

class AuditLog(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    actor: str
    action: str
    target: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIInvocation(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    user: str
    task: str
    model: str
    latency_ms: float
    schema_valid: bool
    repaired: bool
    confirmed: bool
    error: Optional[str] = None
    raw_text: Optional[str] = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- RESOLVED AND VIEWER STATE MODELS (MEMORY.md 5.3) ---

class ReachabilityResolved(BaseModel):
    calls: Calls = Calls.OK
    messages: Messages = Messages.OK
    reason: Optional[str] = None
    until: Optional[datetime] = None
    free_in_min: Optional[int] = None

class ActiveActivityResolved(BaseModel):
    type: ActivityType
    label: str
    until: Optional[datetime] = None
    layer: int
    provenance: Provenance
    visibility: Optional[VisibilitySpec] = None

class ResolvedState(BaseModel):
    owner: str
    as_of: datetime
    activity: Optional[ActiveActivityResolved] = None
    reachability: ReachabilityResolved = Field(default_factory=ReachabilityResolved)
    phone: Dict[str, Any] = Field(default_factory=dict)
    current_place: Optional[str] = None
    travel: Optional[Dict[str, Any]] = None
    exam: Optional[Dict[str, Any]] = None
    last_shared_context: Optional[ContextSnapshot] = None
    next_boundary_at: Optional[datetime] = None
    sharing_paused: bool = False

class ViewerState(BaseModel):
    owner: str
    as_of: datetime
    activity: Optional[Dict[str, Any]] = None
    reachability: Optional[ReachabilityResolved] = None
    phone: Optional[Dict[str, Any]] = None
    current_place: Optional[str] = None
    card_access: Dict[str, str] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    travel: Optional[Dict[str, Any]] = None
    exam: Optional[Dict[str, Any]] = None
    last_shared_context: Optional[ContextSnapshot] = None
    next_boundary_at: Optional[datetime] = None
    sharing_paused: bool = False
