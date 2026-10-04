from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import compute_next_boundary, emit_transition


@workflow.defn
class UserTimelineWorkflow:
    def __init__(self) -> None:
        self.dirty = False

    @workflow.signal
    def timeline_changed(self) -> None:
        self.dirty = True

    @workflow.run
    async def run(self, user_id: str) -> None:
        iterations = 0
        while True:
            boundary = await workflow.execute_activity(
                compute_next_boundary,
                user_id,
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if boundary is None:
                await workflow.wait_condition(lambda: self.dirty)
            else:
                boundary_at = datetime.fromisoformat(boundary)
                delay = max((boundary_at - workflow.now()).total_seconds(), 0)
                if delay > 0:
                    try:
                        await workflow.wait_condition(
                            lambda: self.dirty,
                            timeout=timedelta(seconds=delay),
                        )
                    except asyncio.TimeoutError:
                        await workflow.execute_activity(
                            emit_transition,
                            user_id,
                            boundary,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=RetryPolicy(maximum_attempts=3),
                        )
                else:
                    await workflow.execute_activity(
                        emit_transition,
                        user_id,
                        boundary,
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(maximum_attempts=3),
                    )
            self.dirty = False
            iterations += 1
            if iterations >= 500:
                workflow.continue_as_new(user_id)