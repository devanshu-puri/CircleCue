from dataclasses import dataclass
from typing import Optional


@dataclass
class ArrivalWatchInput:
    activity_id: str
    owner_id: str
    eta: str
    grace_min: int = 15
    escalate_min: int = 15
    expected_offline_until: Optional[str] = None