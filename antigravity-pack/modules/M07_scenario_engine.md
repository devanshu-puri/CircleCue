# M07: Custom scenario engine
**Depends on:** M04, M05, M06.

## Build
1. Scenario DSL as Pydantic (MEMORY section 5 + catalog F9): trigger (time | activity_state | battery | manual), conditions, effects (set_activity, set_availability, suppress_notifications, notify, create_reminder), audience (all_granted | only | except; by user or relationship), notification_rule (always | first_only | never | only_if_called), duration, priority.
2. CRUD `/scenarios`, enable/disable/pause, `dry_run` preview ("would fire Fri 7-10 PM; audience: Mom, Rahul; effects: ...").
3. NL creation: `/ai/parse mode=scenario` returns a ScenarioDraft; `/ai/confirm` stores it. Draft preview must render in plain English so the user verifies understanding.
4. **Time triggers (P0):** expand scenario windows like templates (kind SCENARIO_TIME) so the resolver layer 5 and `next_boundary_at` include them; effects apply while the window is active; Temporal timeline workflow fires START/END events.
5. **Event triggers (P1):** `activity_state` (e.g., studying > 120 min) and `battery` evaluated on bus events.
6. **Guards:** audience is intersected with existing grants (`visibility.viewers_for`); dropped entries are reported in the draft as warnings ("Dad can't see Live Activity; grant first?"); never auto-grant. Conflict resolution: priority, then specificity, then most restrictive. Log each fire in `audit_log`.
7. `suppress_notifications` integrates with M08 pipeline as a pre-filter. `only_if_called` marks the state so viewers see "asked not to be called" and (P1) can use **Urgent override** which emits URGENT_OVERRIDE (rate-limited, owner can disable per viewer).

## Edge cases
Overlapping scenarios; scenario creating availability stricter than manual override (manual wins unless expired); deleted/paused scenario mid-window ends effects immediately; recurrence on exam days.
## Tests: DSL validation, dry-run, conflict resolution, grant intersection, the cricket Friday example end-to-end.
## DoD: demo workflow 5 passes. Update MEMORY.md.
