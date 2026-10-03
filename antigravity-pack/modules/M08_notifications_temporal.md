# M08: Notification engine + Temporal workflows + live delivery
**Depends on:** M03-M07. Temporal is a judged category: make its use real and visible.

## A. Notification pipeline (`domain/notifications.py`), single path
Event -> candidates (`visibility.viewers_for`) -> significance (deterministic table per kind; AI judge only for custom/free text) -> scenario suppression -> dedupe (key `owner:viewer:kind:entity:window`) -> rate limit (per owner-viewer pair/day) -> viewer quiet hours (ARRIVAL_MISSING / URGENT bypass) -> render from the REDACTED ViewerState via templates -> suggested action (CALL, MESSAGE, REMIND_LATER, NONE) -> persist -> **re-check grant** -> deliver.
Copy rules: neutral, non-alarming ("Arrival confirmation is missing", "Sharing paused"); always say when info is from the last share ("Last shared 6:42 PM").
Examples: "Arjun is on break (free ~25 min). Call?" | "Arjun has an exam until 2 PM. May be free after." | "Arjun's phone may go offline. He's heading home with Rahul, ETA 40 min." | "Arjun has arrived home."
Delivery: persist + **SSE** `/notifications/stream` filtered per connected user (re-check grants per event). `GET /notifications`, `POST /notifications/{id}/read|action`. Web push (VAPID/pywebpush) is P1 behind the same interface.
Table of kinds/significance lives in one file and is unit tested.

## B. Temporal (verify SDK API in docs before coding)
Worker runs as separate process (`workflows/worker.py`), task queue `app-main`. Connect to Temporal Cloud (API key/TLS per docs) or local dev server by env.
1. **`UserTimelineWorkflow(user_id)`** long-running, one per user (started at register/first schedule; id `timeline-{user_id}`):
   loop: activity `compute_next_boundary` -> `workflow.wait_condition(lambda: self.dirty, timeout=until_boundary)` -> if timeout: activity `emit_transition(user_id, boundary_id)` (runs resolver at the boundary, publishes DomainEvent -> pipeline, evaluates FREE_NOW, expired-activity prompt, scenario start/end, connection-reminder check) -> continue_as_new after N iterations/daily. Signal `timeline_changed` sets `dirty` (API sends it after any write that can change the timeline).
2. **`ArrivalWatchWorkflow(activity_id)`** (id `arrival-{activity_id}`): signals `delay(new_eta)`, `arrived`, `cancel`, `plan_changed`; timers: at ETA+grace -> activity `nudge_owner`; at +escalate -> activity `notify_viewers(ARRIVAL_MISSING)`; skip escalation inside `expected_offline_window`; on late `arrived` after escalation -> `ALL_CLEAR`. Query `status`.
3. **`PromiseWorkflow(message_id)`** [P1]: wait until `promise_at+5min`; if not done -> notify owner (PROMISE_DUE) and flag receiver-visible "Call pending".
4. Activities are idempotent (dedupe keys), with retry policy + timeouts; DB access only in activities. Workflow code deterministic (use `workflow.now()`, no random, no I/O).
5. API integration via `workflows/client.py`: `ensure_timeline(user_id)`, `signal_timeline_changed`, `start_arrival_watch`, `signal_*`. If Temporal is unreachable: log to Sentry, API still succeeds (resolver keeps UI correct), mark `needs_resync`; a startup task re-ensures timelines.
6. Capture a Temporal UI screenshot of a real run (e.g., ArrivalWatch with signals) for the write-up. Tag Sentry spans/errors in activities with workflow id (no personal text).

## Edge cases
Duplicate boundary fires (idempotency), clock jump with DemoClock (`/dev/tick` triggers `emit_transition` manually), user deleted (terminate workflows), grant revoked between emit and deliver, owner paused sharing (event persisted for owner timeline, no viewer delivery).
## Tests: pipeline table tests; workflow tests using Temporal's test environment with time skipping (verify in docs); integration: break boundary -> mom notified; delayed trip -> single TRAVEL_DELAYED; missing arrival -> nudge then escalate then ALL_CLEAR.
## DoD: demo workflows 1 and 3 work end to end with real timers (2-minute demo events) and via /dev/tick. Update MEMORY.md.
