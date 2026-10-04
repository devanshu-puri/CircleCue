"""Best-effort Temporal client boundary; callers keep the API usable offline."""
import asyncio
import logging
import sentry_sdk

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from app.config import settings
from app.workflows.arrival_watch import ArrivalWatchWorkflow
from app.workflows.inputs import ArrivalWatchInput
from app.workflows.promise import PromiseWorkflow
from app.workflows.user_timeline import UserTimelineWorkflow

logger = logging.getLogger("circlecue.temporal")


class TemporalUnavailable(RuntimeError):
    pass


_client: Client | None = None
_client_lock = asyncio.Lock()


async def connect_client() -> Client:
    global _client
    if not settings.TEMPORAL_ENABLED:
        raise TemporalUnavailable("Temporal integration is disabled")
    if _client:
        return _client
    try:
        async with _client_lock:
            if _client:
                return _client
            _client = await asyncio.wait_for(
                Client.connect(
                    settings.TEMPORAL_ADDRESS,
                    namespace=settings.TEMPORAL_NAMESPACE,
                    api_key=settings.TEMPORAL_API_KEY,
                    tls=True if settings.TEMPORAL_API_KEY else None,
                ),
                timeout=3,
            )
            return _client
    except Exception as exc:
        raise TemporalUnavailable("Could not connect to Temporal") from exc


async def ensure_timeline(user_id: str) -> None:
    client = await connect_client()
    await asyncio.wait_for(
        client.start_workflow(
            UserTimelineWorkflow.run,
            user_id,
            id=f"timeline-{user_id}",
            task_queue="app-main",
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        ),
        timeout=2,
    )


async def signal_timeline_changed(user_id: str) -> None:
    client = await connect_client()
    handle = await asyncio.wait_for(
        client.start_workflow(
            UserTimelineWorkflow.run,
            user_id,
            id=f"timeline-{user_id}",
            task_queue="app-main",
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        ),
        timeout=2,
    )
    await asyncio.wait_for(handle.signal(UserTimelineWorkflow.timeline_changed), timeout=2)


async def start_arrival_watch(input: ArrivalWatchInput) -> None:
    client = await connect_client()
    await asyncio.wait_for(
        client.start_workflow(
            ArrivalWatchWorkflow.run,
            input,
            id=f"arrival-{input.activity_id}",
            task_queue="app-main",
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        ),
        timeout=2,
    )


async def signal_arrival_watch(activity_id: str, signal_name: str, *args) -> None:
    signal = {
        "delay": ArrivalWatchWorkflow.delay,
        "plan_changed": ArrivalWatchWorkflow.plan_changed,
        "arrived": ArrivalWatchWorkflow.arrived,
        "cancel": ArrivalWatchWorkflow.cancel,
        "offline_window": ArrivalWatchWorkflow.offline_window,
    }.get(signal_name)
    if signal is None:
        raise ValueError("Unsupported Arrival Watch signal")
    client = await connect_client()
    handle = client.get_workflow_handle(f"arrival-{activity_id}")
    await asyncio.wait_for(handle.signal(signal, *args), timeout=2)


async def start_promise_watch(message_id: str, promise_at: str) -> None:
    client = await connect_client()
    await asyncio.wait_for(
        client.start_workflow(
            PromiseWorkflow.run,
            args=[message_id, promise_at],
            id=f"promise-{message_id}",
            task_queue="app-main",
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        ),
        timeout=2,
    )


async def signal_promise_done(message_id: str) -> None:
    client = await connect_client()
    handle = client.get_workflow_handle(f"promise-{message_id}")
    await asyncio.wait_for(handle.signal(PromiseWorkflow.mark_done), timeout=2)


async def signal_promise_cancel(message_id: str) -> None:
    client = await connect_client()
    handle = client.get_workflow_handle(f"promise-{message_id}")
    await asyncio.wait_for(handle.signal(PromiseWorkflow.cancel), timeout=2)


async def terminate_user_workflows(user_id: str) -> None:
    if not settings.TEMPORAL_ENABLED:
        return
    try:
        client = await connect_client()
        handle = client.get_workflow_handle(f"timeline-{user_id}")
        await asyncio.wait_for(handle.terminate(reason="User account deleted"), timeout=2)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.warning(
            "Could not terminate user timeline workflow",
            extra={"user_id": user_id, "error_type": type(exc).__name__},
        )


async def resync_timelines(db) -> int:
    """Re-ensure timeline workflows exist for all users or those marked needs_resync."""
    if not settings.TEMPORAL_ENABLED:
        return 0
    resynced = 0
    try:
        users = await db.users.find({"needs_resync": True}).to_list(length=500)
        for user in users:
            uid = str(user["_id"])
            try:
                await ensure_timeline(uid)
                await db.users.update_one({"_id": uid}, {"$unset": {"needs_resync": ""}})
                resynced += 1
            except Exception:
                pass
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
    return resynced