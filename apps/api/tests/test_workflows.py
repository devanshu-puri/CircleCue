from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from app.clock import DemoClock, set_global_clock
from app.config import settings
from app.domain.events import DomainEvent
from app.domain.models import AccessLevel, CardGrants, Grant, NotifyFlags
from app.domain.notifications import process_event
from app.main import app
from app.workflows.activities import (
    emit_transition,
    mark_all_clear,
    notify_arrival_missing,
    nudge_owner,
)
from app.workflows.arrival_watch import ArrivalWatchWorkflow
from app.workflows.client import (
    TemporalUnavailable,
    connect_client,
    terminate_user_workflows,
)
from app.workflows.inputs import ArrivalWatchInput
from app.workflows.promise import PromiseWorkflow
from app.workflows.user_timeline import UserTimelineWorkflow


@pytest.mark.asyncio
async def test_temporal_client_is_disabled_without_explicit_configuration(monkeypatch):
    monkeypatch.setattr(settings, "TEMPORAL_ENABLED", False)

    with pytest.raises(TemporalUnavailable, match="disabled"):
        await connect_client()


def test_workflow_types_expose_expected_signal_and_query_handlers():
    assert callable(UserTimelineWorkflow.timeline_changed)
    assert callable(ArrivalWatchWorkflow.delay)
    assert callable(ArrivalWatchWorkflow.arrived)
    assert callable(ArrivalWatchWorkflow.status)
    assert callable(PromiseWorkflow.mark_done)
    assert callable(PromiseWorkflow.cancel)
    assert callable(PromiseWorkflow.status)


@pytest.mark.asyncio
async def test_arrival_watch_workflow_lifecycle_with_time_skipping():
    nudges: list[str] = []
    escalations: list[str] = []
    clears: list[str] = []

    @activity.defn(name="nudge_owner")
    async def mock_nudge_owner(act_id: str) -> None:
        nudges.append(act_id)

    @activity.defn(name="notify_arrival_missing")
    async def mock_notify_arrival_missing(act_id: str) -> int:
        escalations.append(act_id)
        return 1

    @activity.defn(name="mark_all_clear")
    async def mock_mark_all_clear(act_id: str) -> int:
        clears.append(act_id)
        return 1

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="arrival-test-queue",
            workflows=[ArrivalWatchWorkflow],
            activities=[mock_nudge_owner, mock_notify_arrival_missing, mock_mark_all_clear],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            now = datetime.now(timezone.utc)
            eta = (now + timedelta(seconds=1)).isoformat()
            input_data = ArrivalWatchInput(
                activity_id="act-test-123",
                owner_id="owner-123",
                eta=eta,
                grace_min=1,
                escalate_min=1,
            )

            handle = await env.client.start_workflow(
                ArrivalWatchWorkflow.run,
                input_data,
                id="test-arrival-lifecycle",
                task_queue="arrival-test-queue",
            )

            # Wait for nudge and escalation activities via time-skipping
            await env.sleep(timedelta(minutes=3))
            assert "act-test-123" in nudges
            assert "act-test-123" in escalations

            # Send arrived signal
            await handle.signal(ArrivalWatchWorkflow.arrived)
            await handle.result()

            # Confirm all-clear activity executed on late arrival
            assert "act-test-123" in clears

            # Query final status
            status = await handle.query(ArrivalWatchWorkflow.status)
            assert status["arrived"] is True
            assert status["escalated"] is True


@pytest.mark.asyncio
async def test_promise_workflow_cancelled_before_expiry():
    notified: list[str] = []

    @activity.defn(name="check_and_notify_promise")
    async def mock_check_and_notify_promise(msg_id: str) -> int:
        notified.append(msg_id)
        return 1

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="promise-test-queue",
            workflows=[PromiseWorkflow],
            activities=[mock_check_and_notify_promise],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            now = datetime.now(timezone.utc)
            promise_at = (now + timedelta(minutes=1)).isoformat()

            handle = await env.client.start_workflow(
                PromiseWorkflow.run,
                args=["msg-123", promise_at],
                id="test-promise-cancel",
                task_queue="promise-test-queue",
            )

            # Signal done before timer fires
            await handle.signal(PromiseWorkflow.mark_done)
            await handle.result()

            assert notified == []
            status = await handle.query(PromiseWorkflow.status)
            assert status["done"] is True


@pytest.mark.asyncio
async def test_promise_workflow_fires_when_not_done():
    notified: list[str] = []

    @activity.defn(name="check_and_notify_promise")
    async def mock_check_and_notify_promise(msg_id: str) -> int:
        notified.append(msg_id)
        return 1

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="promise-test-queue-2",
            workflows=[PromiseWorkflow],
            activities=[mock_check_and_notify_promise],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            now = datetime.now(timezone.utc)
            promise_at = (now + timedelta(seconds=2)).isoformat()

            handle = await env.client.start_workflow(
                PromiseWorkflow.run,
                args=["msg-456", promise_at],
                id="test-promise-fire",
                task_queue="promise-test-queue-2",
            )

            await env.sleep(timedelta(minutes=6))
            await handle.result()

            assert "msg-456" in notified


@pytest.mark.asyncio
async def test_integration_break_boundary_notifies_mom(mock_db):
    """Break boundary -> mom notified."""
    owner_id = "student-arjun"
    mom_id = "mom-priya"

    # Set up user records
    mock_db.users.docs[owner_id] = {
        "_id": owner_id,
        "name": "Arjun",
        "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs[mom_id] = {
        "_id": mom_id,
        "name": "Priya",
        "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }

    # Mutual connection
    await mock_db.connections.insert_one({
        "_id": "conn-arjun-priya",
        "a": owner_id,
        "b": mom_id,
        "status": "active",
    })

    # Mom has exam status grant with exam notifications enabled
    await mock_db.grants.insert_one({
        "_id": "grant-arjun-priya",
        "owner": owner_id,
        "viewer": mom_id,
        "cards": {"exam": "status"},
        "notify": {"exam": True},
        "revoked_at": None,
        "expires_at": None,
    })

    # Set up exam set with an exam from 09:00-11:00 and break 11:00-11:30
    await mock_db.exam_sets.insert_one({
        "_id": "exam-set-1",
        "owner": owner_id,
        "date": "2026-10-04",
        "items": [
            {"type": "exam", "subject": "Physics", "start_local": "09:00", "end_local": "11:00", "calls_ok": False},
            {"type": "break", "subject": "Lunch Break", "start_local": "11:00", "end_local": "11:30", "calls_ok": True},
        ],
        "pre_buffer_min": 0,
        "post_buffer_min": 0,
        "keep_schedule": False,
        "version": 1,
    })

    # Injected clock set to break boundary (11:00 UTC)
    break_time = datetime(2026, 10, 4, 11, 0, tzinfo=timezone.utc)
    set_global_clock(DemoClock(initial_offset=break_time - datetime.now(timezone.utc)))

    # Emit transition at boundary
    emitted = await emit_transition(owner_id, "boundary-1100")
    assert emitted >= 1

    # Check Mom received EXAM_BREAK notification
    mom_notifications = [n for n in mock_db.notifications.docs.values() if n.get("to") == mom_id]
    assert len(mom_notifications) == 1
    assert mom_notifications[0]["kind"] == "EXAM_BREAK"
    assert mom_notifications[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_integration_delayed_trip_single_travel_delayed(mock_db):
    """Delayed trip -> single TRAVEL_DELAYED notification due to deduplication."""
    owner_id = "traveler-1"
    friend_id = "friend-1"
    now = datetime(2026, 10, 4, 14, 0, tzinfo=timezone.utc)

    mock_db.users.docs[owner_id] = {
        "_id": owner_id, "name": "Traveler", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs[friend_id] = {
        "_id": friend_id, "name": "Friend", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    await mock_db.connections.insert_one({
        "_id": "conn-tf", "a": owner_id, "b": friend_id, "status": "active",
    })
    await mock_db.grants.insert_one({
        "_id": "grant-tf", "owner": owner_id, "viewer": friend_id,
        "cards": {"travel": "status"},
        "notify": {"travel": True},
        "revoked_at": None, "expires_at": None,
    })

    # Travel delayed event
    event = DomainEvent("TRAVEL_DELAYED", owner_id, "trip-1", occurred_at=now)

    first = await process_event(mock_db, event, now)
    second = await process_event(mock_db, event, now)

    assert len(first) == 1
    assert len(second) == 0
    friend_notifications = [n for n in mock_db.notifications.docs.values() if n.get("to") == friend_id]
    assert len(friend_notifications) == 1
    assert friend_notifications[0]["kind"] == "TRAVEL_DELAYED"


@pytest.mark.asyncio
async def test_integration_missing_arrival_nudge_then_escalate_then_all_clear(mock_db):
    """Missing arrival -> nudge then escalate then ALL_CLEAR."""
    owner_id = "night-traveler"
    parent_id = "parent-1"
    now = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)
    set_global_clock(DemoClock(initial_offset=now - datetime.now(timezone.utc)))

    mock_db.users.docs[owner_id] = {
        "_id": owner_id, "name": "Night Traveler", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "23:00"},
        "sharing_paused": {"active": False},
    }
    mock_db.users.docs[parent_id] = {
        "_id": parent_id, "name": "Parent", "tz": "UTC",
        "routine_prefs": {"wake": "07:00", "sleep": "06:00"}, # inside quiet hours normally
        "sharing_paused": {"active": False},
    }
    await mock_db.connections.insert_one({
        "_id": "conn-np", "a": owner_id, "b": parent_id, "status": "active",
    })
    await mock_db.grants.insert_one({
        "_id": "grant-np", "owner": owner_id, "viewer": parent_id,
        "cards": {"safety": "status"},
        "notify": {"safety": True},
        "revoked_at": None, "expires_at": None,
    })

    act_id = "trip-night-1"
    await mock_db.activities.insert_one({
        "_id": act_id,
        "owner": owner_id,
        "type": "TRAVEL",
        "title": "Heading home",
        "status": "ACTIVE",
        "phase": "travelling",
        "start_at": now,
        "expected_end_at": now + timedelta(minutes=30),
        "check_on_me": {"enabled": True, "grace_min": 15, "escalate_min": 15},
        "version": 1,
    })

    # Step 1: Nudge owner
    await nudge_owner(act_id)
    owner_notifs = [n for n in mock_db.notifications.docs.values() if n.get("to") == owner_id]
    assert len(owner_notifs) == 1
    assert owner_notifs[0]["payload_redacted"]["text"] == "Did you arrive?"

    # Step 2: Escalate (parent notified even during quiet hours)
    escalated_count = await notify_arrival_missing(act_id)
    assert escalated_count == 1
    parent_notifs = [n for n in mock_db.notifications.docs.values() if n.get("to") == parent_id and n.get("kind") == "ARRIVAL_MISSING"]
    assert len(parent_notifs) == 1
    assert "missing" in parent_notifs[0]["payload_redacted"]["text"].lower()

    # Step 3: Owner arrives late -> ALL_CLEAR delivered to parent
    clear_count = await mark_all_clear(act_id)
    assert clear_count == 1
    parent_clear = [n for n in mock_db.notifications.docs.values() if n.get("to") == parent_id and n.get("kind") == "ALL_CLEAR"]
    assert len(parent_clear) == 1
    assert "all good" in parent_clear[0]["payload_redacted"]["text"].lower()


@pytest.mark.asyncio
async def test_terminate_user_workflows_handles_unconfigured_temporal():
    # Should not raise exception
    await terminate_user_workflows("nonexistent-user")