from datetime import datetime, timezone, timedelta
import pytest

from app.domain.models import (
    ResolvedState, ViewerState, Grant, CardGrants, AccessLevel, CardKey,
    ActivityType, ReachabilityResolved, ActiveActivityResolved, Provenance,
    ProvenanceSource, Calls, Messages, VisibilitySpec, ContextSnapshot
)
from app.domain.visibility import (
    is_grant_active, can_view, project, activity_card_for_type, viewers_for,
)

def test_is_grant_active():
    now = datetime.now(timezone.utc)
    
    # 1. Active grant
    active_grant = Grant(owner="u1", viewer="u2", cards=CardGrants())
    assert is_grant_active(active_grant, now) is True

    # 2. Revoked grant
    revoked_grant = Grant(owner="u1", viewer="u2", cards=CardGrants(), revoked_at=now)
    assert is_grant_active(revoked_grant, now) is False

    # 3. Expired grant
    expired_grant = Grant(owner="u1", viewer="u2", cards=CardGrants(), expires_at=now - timedelta(seconds=1))
    assert is_grant_active(expired_grant, now) is False

    # 4. None grant
    assert is_grant_active(None, now) is False

def test_can_view_matrix():
    now = datetime.now(timezone.utc)
    
    # Grant with STATUS level for travel, DETAILS for live, NONE for exam
    grant = Grant(
        owner="u1",
        viewer="u2",
        cards=CardGrants(
            travel=AccessLevel.STATUS,
            live=AccessLevel.DETAILS,
            exam=AccessLevel.NONE
        )
    )

    # Travel Card
    assert can_view(grant, CardKey.TRAVEL, AccessLevel.STATUS, now) is True
    assert can_view(grant, CardKey.TRAVEL, AccessLevel.DETAILS, now) is False

    # Live Card
    assert can_view(grant, CardKey.LIVE, AccessLevel.STATUS, now) is True
    assert can_view(grant, CardKey.LIVE, AccessLevel.DETAILS, now) is True

    # Exam Card
    assert can_view(grant, CardKey.EXAM, AccessLevel.STATUS, now) is False
    assert can_view(grant, CardKey.EXAM, AccessLevel.DETAILS, now) is False

def test_can_view_all_cards_and_levels():
    now = datetime.now(timezone.utc)
    for card in CardKey:
        for granted_level in AccessLevel:
            grant = Grant(
                owner="u1",
                viewer="u2",
                cards=CardGrants(**{card.value: granted_level}),
            )
            assert can_view(grant, card, AccessLevel.NONE, now) is False
            assert can_view(grant, card, AccessLevel.STATUS, now) is (
                granted_level in (AccessLevel.STATUS, AccessLevel.DETAILS)
            )
            assert can_view(grant, card, AccessLevel.DETAILS, now) is (
                granted_level == AccessLevel.DETAILS
            )

def test_project_sharing_paused():
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(owner="u1", as_of=now, sharing_paused=True)
    grant = Grant(owner="u1", viewer="u2", cards=CardGrants(live=AccessLevel.DETAILS))

    viewer_state = project(resolved, grant, now, viewer_id="u2")
    assert viewer_state.sharing_paused is True
    assert viewer_state.activity["label"] == "Sharing paused"
    assert viewer_state.phone is None
    assert viewer_state.travel is None

def test_project_does_not_reveal_pause_without_matching_grant():
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(owner="u1", as_of=now, sharing_paused=True)

    viewer_state = project(resolved, None, now, viewer_id="u2")

    assert viewer_state.sharing_paused is False
    assert viewer_state.activity is None

def test_project_zero_access_when_no_grant():
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(
        owner="u1",
        as_of=now,
        activity=ActiveActivityResolved(
            type=ActivityType.STUDY,
            label="Physics Revision",
            until=now + timedelta(hours=1),
            layer=2,
            provenance=Provenance(source=ProvenanceSource.USER_SHARED)
        )
    )

    # No grant passed
    viewer_state = project(resolved, None, now, viewer_id="u2")
    assert viewer_state.activity is None
    assert viewer_state.reachability is None
    assert viewer_state.phone is None

def test_project_hides_state_metadata_from_grant_without_card_access():
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(
        owner="u1",
        as_of=now,
        last_shared_context=ContextSnapshot(
            snapshot={"activity": "Exam"},
            shared_at=now - timedelta(minutes=1),
        ),
        next_boundary_at=now + timedelta(hours=1),
    )
    grant = Grant(owner="u1", viewer="u2", cards=CardGrants())

    viewer_state = project(resolved, grant, now, viewer_id="u2")

    assert viewer_state.last_shared_context is None
    assert viewer_state.next_boundary_at is None

def test_project_rejects_grant_for_different_owner_or_viewer():
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(owner="u1", as_of=now)
    mismatched_grants = [
        Grant(owner="u3", viewer="u2", cards=CardGrants(live=AccessLevel.DETAILS)),
        Grant(owner="u1", viewer="u3", cards=CardGrants(live=AccessLevel.DETAILS)),
    ]

    for grant in mismatched_grants:
        viewer_state = project(resolved, grant, now, viewer_id="u2")
        assert viewer_state.activity is None
        assert viewer_state.last_shared_context is None
        assert viewer_state.next_boundary_at is None

@pytest.mark.asyncio
async def test_viewers_for_requires_active_connection_and_active_card_grant(mock_db):
    now = datetime.now(timezone.utc)
    await mock_db.connections.insert_one({
        "_id": "active-connection", "a": "owner", "b": "connected",
        "status": "active",
    })
    await mock_db.connections.insert_one({
        "_id": "blocked-connection", "a": "owner", "b": "blocked",
        "status": "blocked",
    })
    for viewer, revoked_at, expires_at in [
        ("connected", None, None),
        ("blocked", None, None),
        ("unconnected", None, None),
        ("revoked", now, None),
        ("expired", None, now - timedelta(seconds=1)),
    ]:
        await mock_db.grants.insert_one({
            "_id": f"grant-{viewer}",
            "owner": "owner",
            "viewer": viewer,
            "cards": {"travel": "status"},
            "revoked_at": revoked_at,
            "expires_at": expires_at,
        })

    viewers = await viewers_for(
        mock_db, "owner", CardKey.TRAVEL, AccessLevel.STATUS, now
    )

    assert viewers == ["connected"]

def test_project_status_vs_details_levels():
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=2)
    
    resolved = ResolvedState(
        owner="u1",
        as_of=now,
        activity=ActiveActivityResolved(
            type=ActivityType.TRAVEL,
            label="Heading to College",
            until=until,
            layer=3,
            provenance=Provenance(source=ProvenanceSource.USER_SHARED)
        ),
        phone={
            "mode": "normal",
            "battery_pct": 14,
            "battery_bucket": "low",
            "may_go_offline": True,
            "declared_offline": False
        },
        current_place="Library",
        travel={
            "destination": "College Campus, Gate 2",
            "destination_kind": "college",
            "eta": until.isoformat(),
            "phase": "travelling",
            "overdue": False,
            "driver_name": "Ramesh",
            "driver_phone": "+919876543210"
        }
    )

    # Grant: Travel = STATUS, Phone = DETAILS
    grant_status = Grant(
        owner="u1",
        viewer="u2",
        cards=CardGrants(travel=AccessLevel.STATUS, phone=AccessLevel.DETAILS)
    )

    viewer_state = project(resolved, grant_status, now, viewer_id="u2")
    
    # Travel is projected at STATUS level (destination string & driver details hidden!)
    assert viewer_state.travel is not None
    assert viewer_state.travel["destination_kind"] == "college"
    assert "destination" not in viewer_state.travel
    assert "driver_name" not in viewer_state.travel
    assert viewer_state.current_place is None

    # Phone is projected at DETAILS level (exact battery_pct shown!)
    assert viewer_state.phone is not None
    assert viewer_state.phone["battery_pct"] == 14

    grant_details = Grant(owner="u1", viewer="u2", cards=CardGrants(travel=AccessLevel.DETAILS))
    details_state = project(resolved, grant_details, now, viewer_id="u2")
    assert details_state.current_place == "Library"

def test_project_private_label_and_visibility_only():
    now = datetime.now(timezone.utc)
    
    # Activity with mode = 'only' restricted to 'u3'
    act_only = ActiveActivityResolved(
        type=ActivityType.STUDY,
        label="Secret Exam Prep",
        until=now + timedelta(hours=1),
        layer=2,
        provenance=Provenance(source=ProvenanceSource.USER_SHARED)
    )
    # Inject visibility spec onto act_only
    setattr(act_only, "visibility", VisibilitySpec(mode="only", viewer_ids=["u3"]))

    resolved = ResolvedState(owner="u1", as_of=now, activity=act_only)
    grant = Grant(owner="u1", viewer="u2", cards=CardGrants(live=AccessLevel.DETAILS))

    # u2 is NOT in viewer_ids -> activity redacted!
    viewer_state_u2 = project(resolved, grant, now, viewer_id="u2")
    assert viewer_state_u2.activity is None

    # u3 IS in viewer_ids -> activity visible!
    grant_u3 = Grant(owner="u1", viewer="u3", cards=CardGrants(live=AccessLevel.DETAILS))
    viewer_state_u3 = project(resolved, grant_u3, now, viewer_id="u3")
    assert viewer_state_u3.activity is not None
    assert viewer_state_u3.activity["label"] == "Secret Exam Prep"

def test_activity_card_mapping():
    assert activity_card_for_type(ActivityType.CLASS) == CardKey.SCHEDULE
    assert activity_card_for_type(ActivityType.EXAM) == CardKey.EXAM
    assert activity_card_for_type(ActivityType.TRAVEL) == CardKey.TRAVEL
    assert activity_card_for_type(ActivityType.STUDY) == CardKey.LIVE


@pytest.mark.parametrize(
    ("activity_type", "card", "detail_field"),
    [
        (ActivityType.CLASS, CardKey.SCHEDULE, "provenance"),
        (ActivityType.STUDY, CardKey.LIVE, "provenance"),
        (ActivityType.EXAM, CardKey.EXAM, "subject"),
        (ActivityType.TRAVEL, CardKey.TRAVEL, "destination"),
        (ActivityType.PHONE_STATUS, CardKey.PHONE, "battery_pct"),
        (ActivityType.SAFETY, CardKey.SAFETY, "provenance"),
    ],
)
def test_each_state_card_redacts_status_and_restores_details(activity_type, card, detail_field):
    now = datetime.now(timezone.utc)
    resolved = ResolvedState(
        owner="u1",
        as_of=now,
        activity=ActiveActivityResolved(
            type=activity_type,
            label="Private label",
            until=now + timedelta(hours=1),
            layer=2,
            provenance=Provenance(source=ProvenanceSource.USER_SHARED),
        ),
        phone={"mode": "normal", "battery_pct": 5, "battery_bucket": "dying"},
        travel={
            "destination": "Home", "destination_kind": "home",
            "companions": ["u3"], "vehicle_number": "CAB-12",
            "companion_phone": "+1 555 0100",
            "expected_return_at": "2026-10-05T10:00:00+00:00",
        },
        exam={"state": "in_progress", "subject": "Physics", "exams_today": 1},
    )
    status_grant = Grant(
        owner="u1", viewer="u2",
        cards=CardGrants(**{card.value: AccessLevel.STATUS}),
    )
    details_grant = Grant(
        owner="u1", viewer="u2",
        cards=CardGrants(**{card.value: AccessLevel.DETAILS}),
    )

    status_state = project(resolved, status_grant, now, viewer_id="u2")
    details_state = project(resolved, details_grant, now, viewer_id="u2")

    assert status_state.activity is not None
    assert details_state.activity is not None
    if card == CardKey.TRAVEL:
        assert detail_field not in status_state.travel
        assert details_state.travel[detail_field] == "Home"
        assert "companion_phone" not in status_state.travel
        assert details_state.travel["companion_phone"] == "+1 555 0100"
    elif card == CardKey.PHONE:
        assert detail_field not in status_state.phone
        assert details_state.phone[detail_field] == 5
    elif card == CardKey.EXAM:
        assert detail_field not in status_state.exam
        assert details_state.exam[detail_field] == "Physics"
    else:
        assert detail_field not in status_state.activity
        assert detail_field in details_state.activity
