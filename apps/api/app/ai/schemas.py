"""Typed, persistence-free drafts returned by the AI parsing layer."""
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from app.domain.models import Availability, ExceptionKind, VisibilitySpec


class TimeSpec(BaseModel):
    hh_mm: Optional[str] = Field(default=None, pattern=r"^\d{1,2}(:\d{2})?$")
    date_ref: Optional[str] = None
    relative_min: Optional[int] = Field(default=None, ge=0)
    ampm_assumed: bool = False

    @model_validator(mode="after")
    def require_time_value(self):
        if (self.hh_mm is None) == (self.relative_min is None):
            raise ValueError("Set exactly one of hh_mm or relative_min")
        return self


class Missing(BaseModel):
    field: str
    question: str


class ActivityDraft(BaseModel):
    kind: Literal["activity"]
    activity_type: str
    title: str
    start: Optional[TimeSpec] = None
    end: Optional[TimeSpec] = None
    resolved_start_at: Optional[str] = None
    resolved_end_at: Optional[str] = None
    availability: Availability = Field(default_factory=Availability)
    visibility: VisibilitySpec = Field(default_factory=VisibilitySpec)


class TravelDraft(BaseModel):
    kind: Literal["travel"]
    title: str = "Travelling"
    destination: Optional[str] = None
    destination_kind: str = "other"
    depart: Optional[TimeSpec] = None
    eta: Optional[TimeSpec] = None
    companion: Optional[str] = None
    companion_id: Optional[str] = None
    mode: str = "cab"
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    expected_offline_window: Optional[Dict[str, TimeSpec]] = None
    check_on_me: bool = False
    resolved_depart_at: Optional[str] = None
    resolved_eta_at: Optional[str] = None


class PhoneDraft(BaseModel):
    kind: Literal["phone"]
    battery_pct: Optional[int] = Field(default=None, ge=0, le=100)
    mode: Optional[str] = None
    calls: Optional[Literal["ok", "prefer_not", "no"]] = None
    messages: Optional[Literal["ok", "later"]] = None
    may_go_offline: bool = False
    declared_offline: bool = False
    until: Optional[TimeSpec] = None
    resolved_until: Optional[str] = None


class ExceptionDraft(BaseModel):
    kind: Literal["exception"]
    exception_kind: ExceptionKind
    date: Optional[TimeSpec] = None
    template_id: Optional[str] = None
    new_start: Optional[TimeSpec] = None
    new_end: Optional[TimeSpec] = None
    note: Optional[str] = None
    resolved_date: Optional[str] = None
    resolved_new_start: Optional[str] = None
    resolved_new_end: Optional[str] = None


class ScenarioDraft(BaseModel):
    kind: Literal["scenario"]
    name: str
    trigger: Dict[str, object] = Field(default_factory=dict)
    conditions: List[Dict[str, object]] = Field(default_factory=list)
    effects: List[Dict[str, object]] = Field(default_factory=list)
    audience: List[str] = Field(default_factory=list)
    audience_mode: Literal["all_granted", "only", "except"] = "all_granted"
    notification_rule: Literal["always", "first_only", "never", "only_if_called"] = "always"
    priority: int = Field(default=50, ge=0, le=100)


class MessageDraft(BaseModel):
    kind: Literal["message"]
    text: Optional[str] = None
    template_key: Optional[str] = None
    audience: List[str] = Field(default_factory=list)
    promise_at: Optional[TimeSpec] = None
    resolved_promise_at: Optional[str] = None


class ReminderDraft(BaseModel):
    kind: Literal["reminder"]
    target: Optional[str] = None
    title: str
    due: Optional[TimeSpec] = None
    resolved_due: Optional[str] = None


DraftItem = Annotated[
    Union[
        ActivityDraft,
        TravelDraft,
        PhoneDraft,
        ExceptionDraft,
        ScenarioDraft,
        MessageDraft,
        ReminderDraft,
    ],
    Field(discriminator="kind"),
]


class ParseResult(BaseModel):
    intent: Literal[
        "activity", "travel", "phone", "exception", "scenario",
        "message", "reminder", "unknown",
    ] = "unknown"
    language: str = "unknown"
    items: List[DraftItem] = Field(default_factory=list)
    missing: List[Missing] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: List[str] = Field(default_factory=list)


class SignificanceResult(BaseModel):
    notify: bool
    reason: str = Field(max_length=160)