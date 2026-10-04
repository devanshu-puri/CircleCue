from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import check_and_notify_promise


@workflow.defn
class PromiseWorkflow:
    def __init__(self) -> None:
        self.is_done = False
        self.is_cancelled = False

    @workflow.signal
    def mark_done(self) -> None:
        self.is_done = True

    @workflow.signal
    def cancel(self) -> None:
        self.is_cancelled = True

    @workflow.query
    def status(self) -> dict:
        return {
            "done": self.is_done,
            "cancelled": self.is_cancelled,
        }

    @workflow.run
    async def run(self, message_id: str, promise_at_iso: str) -> None:
        promise_at = datetime.fromisoformat(promise_at_iso)
        due_at = promise_at + timedelta(minutes=5)
        delay = max((due_at - workflow.now()).total_seconds(), 0)
        try:
            await workflow.wait_condition(
                lambda: self.is_done or self.is_cancelled,
                timeout=timedelta(seconds=delay),
            )
        except asyncio.TimeoutError:
            pass

        if not self.is_done and not self.is_cancelled:
            await workflow.execute_activity(
                check_and_notify_promise,
                message_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
