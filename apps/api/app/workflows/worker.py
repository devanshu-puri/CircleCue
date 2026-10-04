"""Standalone Temporal worker process for the app-main task queue."""
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.workflows.activities import (
    check_and_notify_promise,
    compute_next_boundary,
    emit_transition,
    mark_all_clear,
    notify_arrival_missing,
    nudge_owner,
)
from app.workflows.arrival_watch import ArrivalWatchWorkflow
from app.workflows.promise import PromiseWorkflow
from app.workflows.user_timeline import UserTimelineWorkflow


async def run_worker() -> None:
    if not settings.TEMPORAL_ENABLED:
        raise RuntimeError("Set TEMPORAL_ENABLED=true to run the Temporal worker")
    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE,
        api_key=settings.TEMPORAL_API_KEY,
        tls=True if settings.TEMPORAL_API_KEY else None,
    )
    worker = Worker(
        client,
        task_queue="app-main",
        workflows=[UserTimelineWorkflow, ArrivalWatchWorkflow, PromiseWorkflow],
        activities=[
            compute_next_boundary,
            emit_transition,
            nudge_owner,
            notify_arrival_missing,
            mark_all_clear,
            check_and_notify_promise,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())