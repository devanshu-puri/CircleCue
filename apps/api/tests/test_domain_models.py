from datetime import datetime, timezone
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.models import (
    User, Activity, ActivityType, Status, Provenance, ProvenanceSource,
    ResolvedState, ViewerState, Calls, Messages, AccessLevel, TravelMeta,
    ExamMeta, ExceptionItem, ExceptionKind, CardKey
)
from app.cards.registry import CARD_REGISTRY

def test_user_model_valid():
    user = User(
        name="Rahul Sharma",
        user_code="RAHUL123",
        email="rahul@example.com",
        pw_hash="hashed_password",
        tz="Asia/Kolkata"
    )
    assert user.name == "Rahul Sharma"
    assert user.user_code == "RAHUL123"
    assert user.tz == "Asia/Kolkata"

def test_user_name_sanitization():
    user = User(
        name="<script>alert('xss')</script>Arjun",
        user_code="ARJUN123",
        email="arjun@example.com",
        pw_hash="hashed_password"
    )
    assert "<script>" not in user.name
    assert "&lt;script&gt;" in user.name

def test_activity_model_validation():
    now = datetime.now(timezone.utc)
    activity = Activity(
        owner="user_1",
        type=ActivityType.STUDY,
        title="Math Revision",
        status=Status.ACTIVE,
        start_at=now,
        expected_end_at=now,
        provenance=Provenance(source=ProvenanceSource.USER_SHARED)
    )
    assert activity.type == ActivityType.STUDY
    assert activity.title == "Math Revision"
    assert activity.provenance.source == ProvenanceSource.USER_SHARED

def test_activity_title_overlength():
    now = datetime.now(timezone.utc)
    long_title = "A" * 150
    with pytest.raises(PydanticValidationError):
        Activity(
            owner="user_1",
            type=ActivityType.STUDY,
            title=long_title,
            status=Status.ACTIVE,
            start_at=now,
            expected_end_at=now,
            provenance=Provenance(source=ProvenanceSource.USER_SHARED)
        )

def test_travel_metadata_model():
    meta = TravelMeta(
        destination="Home",
        mode="cab",
        companions=["user_2"]
    )
    assert meta.kind == "travel"
    assert meta.destination == "Home"
    assert meta.companions == ["user_2"]

def test_resolved_state_model():
    now = datetime.now(timezone.utc)
    state = ResolvedState(
        owner="user_1",
        as_of=now,
        sharing_paused=False
    )
    assert state.owner == "user_1"
    assert state.sharing_paused is False


def test_card_registry_covers_every_card_without_new_collections():
    assert set(CARD_REGISTRY) == set(CardKey)
    assert all(spec.grant_card == key for key, spec in CARD_REGISTRY.items())
    assert {spec.collection for spec in CARD_REGISTRY.values()} <= {
        "templates", "exam_sets", "activities", "phone_state", "messages",
    }
    assert CARD_REGISTRY[CardKey.TRAVEL].collection == "activities"
    assert CARD_REGISTRY[CardKey.LIVE].collection == "activities"
