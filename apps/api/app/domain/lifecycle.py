from typing import Dict, Set, Optional
from app.domain.models import Status, TravelPhase, ActivityType

# Generic Activity Status Transition Table
STATUS_TRANSITIONS: Dict[Status, Set[Status]] = {
    Status.PLANNED: {Status.ACTIVE, Status.CANCELLED},
    Status.ACTIVE: {
        Status.EXTENDED,
        Status.DELAYED,
        Status.CHANGED,
        Status.COMPLETED,
        Status.CANCELLED,
        Status.EXPIRED,
    },
    Status.EXTENDED: {
        Status.EXTENDED,
        Status.DELAYED,
        Status.CHANGED,
        Status.COMPLETED,
        Status.CANCELLED,
        Status.EXPIRED,
    },
    Status.DELAYED: {
        Status.ACTIVE,
        Status.EXTENDED,
        Status.DELAYED,
        Status.CHANGED,
        Status.COMPLETED,
        Status.CANCELLED,
        Status.EXPIRED,
    },
    Status.CHANGED: {
        Status.ACTIVE,
        Status.EXTENDED,
        Status.DELAYED,
        Status.CHANGED,
        Status.COMPLETED,
        Status.CANCELLED,
        Status.EXPIRED,
    },
    Status.COMPLETED: set(),
    Status.CANCELLED: set(),
    Status.EXPIRED: set(),
}

# Travel Phase Transition Table
TRAVEL_PHASE_TRANSITIONS: Dict[TravelPhase, Set[TravelPhase]] = {
    TravelPhase.PLANNED: {TravelPhase.TRAVELLING, TravelPhase.COMPLETED},
    TravelPhase.TRAVELLING: {
        TravelPhase.DELAYED,
        TravelPhase.ARRIVED,
        TravelPhase.COMPLETED,
    },
    TravelPhase.DELAYED: {
        TravelPhase.TRAVELLING,
        TravelPhase.ARRIVED,
        TravelPhase.COMPLETED,
    },
    TravelPhase.ARRIVED: {TravelPhase.COMPLETED},
    TravelPhase.COMPLETED: set(),
}

def can_transition(
    activity_type: ActivityType,
    from_status: Status,
    to_status: Status
) -> bool:
    """Check if an activity status transition is valid according to lifecycle rules."""
    allowed = STATUS_TRANSITIONS.get(from_status, set())
    return to_status in allowed

def can_transition_travel_phase(
    from_phase: TravelPhase,
    to_phase: TravelPhase
) -> bool:
    """Check if a travel phase transition is valid."""
    allowed = TRAVEL_PHASE_TRANSITIONS.get(from_phase, set())
    return to_phase in allowed
