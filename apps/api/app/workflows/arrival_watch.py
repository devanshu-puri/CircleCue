from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import mark_all_clear, notify_arrival_missing, nudge_owner
    from app.workflows.inputs import ArrivalWatchInput


@workflow.defn
class ArrivalWatchWorkflow:
    def __init__(self) -> None:
        self.eta: Optional[str] = None
        self.offline_until: Optional[str] = None
        self.has_arrived = False
        self.is_cancelled = False
        self.escalated = False

    @workflow.signal
    def delay(self, new_eta: str) -> None:
        self.eta = new_eta

    @workflow.signal
    def plan_changed(self, new_eta: str) -> None:
        self.eta = new_eta

    @workflow.signal
    def arrived(self) -> None:
        self.has_arrived = True

    @workflow.signal
    def cancel(self) -> None:
        self.is_cancelled = True

    @workflow.signal
    def offline_window(self, until: str) -> None:
        self.offline_until = until

    @workflow.query
    def status(self) -> dict:
        return {
            "eta": self.eta,
            "arrived": self.has_arrived,
            "cancelled": self.is_cancelled,
            "escalated": self.escalated,
        }

    @workflow.run
    async def run(self, input: ArrivalWatchInput) -> None:
        self.eta = input.eta
        self.offline_until = input.expected_offline_until
        while not self.has_arrived and not self.is_cancelled:
            watched_eta = self.eta
            watched_offline_until = self.offline_until
            eta = datetime.fromisoformat(watched_eta)
            grace_at = eta + timedelta(minutes=input.grace_min)
            try:
                await workflow.wait_condition(
                    lambda: (
                        self.has_arrived
                        or self.is_cancelled
                        or self.eta != watched_eta
                        or self.offline_until != watched_offline_until
                    ),
                    timeout=max(grace_at - workflow.now(), timedelta(seconds=0)),
                )
                continue
            except asyncio.TimeoutError:
                pass

            if (
                self.has_arrived or self.is_cancelled
                or self.eta != watched_eta
                or self.offline_until != watched_offline_until
            ):
                continue
            await workflow.execute_activity(
                nudge_owner,
                input.activity_id,
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            escalation_at = grace_at + timedelta(minutes=input.escalate_min)
            if self.offline_until:
                offline_until = datetime.fromisoformat(self.offline_until)
                escalation_at = max(escalation_at, offline_until)
            try:
                await workflow.wait_condition(
                    lambda: (
                        self.has_arrived
                        or self.is_cancelled
                        or self.eta != watched_eta
                        or self.offline_until != watched_offline_until
                    ),
                    timeout=max(escalation_at - workflow.now(), timedelta(seconds=0)),
                )
                continue
            except asyncio.TimeoutError:
                pass

            if (
                self.has_arrived or self.is_cancelled
                or self.eta != watched_eta
                or self.offline_until != watched_offline_until
            ):
                continue
            await workflow.execute_activity(
                notify_arrival_missing,
                input.activity_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            self.escalated = True
            await workflow.wait_condition(lambda: (
                self.has_arrived
                or self.is_cancelled
                or self.eta != watched_eta
                or self.offline_until != watched_offline_until
            ))

        if self.has_arrived and self.escalated:
            await workflow.execute_activity(
                mark_all_clear,
                input.activity_id,
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )