# M09: Connection reminders (+ TabPFN best-time-to-call, P1)
**Depends on:** M04 (free windows), M08.

## A. Reminders (P0 basic)
1. `connection_plans` CRUD: target (a connection), importance, rule (manual | daily | weekly days | every N days | routine window), preferred window, snooze/cooldown.
2. Evaluation (called from `emit_transition` when the owner becomes free, and at preferred window edges): conditions: owner currently free/calls ok, not connected under the rule yet, not snoozed, nudges_today < 2, not quiet hours, and **target's state is visible to the owner and not "no calls"** (respect visibility; if not visible, still remind but without target-state claims). Output `CONNECTION_REMINDER` (owner-only) e.g. "You're free now. You haven't connected with Mom today. Call?"
3. Actions: Call (tel: link, then ask "Did you connect?"), Remind in 30 min, Skip today, Mark connected (sets `last_connected_at`). Dismissals double cooldown. Missed connection = planned/promised call not marked.
4. Long-distance: show overlap windows using both users' tz and the target's *visible* sleep window.
5. Honest limits: no call logs; never infer behavior beyond rules.

## B. TabPFN pick-up predictor (P1, only after P0 green)
Real tabular problem: given a viewer's small history of calls to one owner, predict P(picked up) for candidate time slots.
1. `call_events` captured when a viewer taps Call (outcome set by viewer: picked/missed). Features (numeric/categorical only, no PII, only fields the viewer could see): hour, weekday, minutes since owner's visible state started, minutes until it ends, state type, calls-availability, relationship preset.
2. `predict/pickup.py`: `PickupPredictor` interface; `TabPFNPredictor` (start with Prior Labs' client for speed or local package on the DO box; verify install/API in docs; note that features are anonymous), `BaselinePredictor` (hour/weekday prior + logistic regression). Selected by `PREDICTOR_PROVIDER`.
3. `scripts/seed_call_history.py`: clearly-flagged **synthetic** history for demo users (`synthetic=true`, UI badge "demo data"). Never mix synthetic into real users.
4. `GET /predict/best-time?owner=` ranks today's free windows (from `freewindows`) by P(pickup), returns top 3 with probability and a plain reason. Fallback to baseline if TabPFN errors or n < 20.
5. Eval script: time-split holdout, TabPFN vs baseline (AUC/accuracy/log-loss). Put results in `docs/EVAL_REPORT.md` and the write-up. Report honestly if the gain is small.
6. UI: "Best time to call: 5:10-5:30 PM (82%)" on viewer's card, labelled system_inferred.

## DoD: reminder demo (workflow 4) works; if P1: predictor endpoint + eval table. Update MEMORY.md.
