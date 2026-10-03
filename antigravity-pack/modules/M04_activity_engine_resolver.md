# M04: Activity engine, lifecycle, resolver, free windows
**Depends on:** M01, M03. This is the brain. Pure functions, heavy tests.

## Build
1. **Template expansion:** `expand(templates, exceptions, exam_sets, date, tz) -> list[Segment]` handling days-of-week, A/B week pattern, active_from/to, exceptions (cancelled/moved/extended/early_end/day_off), exam override of that date's schedule (unless keep_schedule).
2. **`resolver.resolve(user_bundle, now) -> ResolvedState`** implementing MEMORY 5.2 precedence and reachability merge. Includes: schedule-derived states (in class, lab, break, lunch, free, finished, not started, holiday), exam states (in progress, between exams, upcoming, finished, exams_today count, pre/post buffers), travel overdue flag, expired manual activity fallthrough, phone staleness, `last_shared_context` selection, `next_boundary_at` (earliest of: next segment edge, activity end, exam edge, ETA, snapshot stale time).
3. **`freewindows.py`:** `free_windows(date, min_window, buffer) -> list[Window]`, `free_in_minutes`. Used for FREE_NOW and for reminders.
4. **Lifecycle service:** `transition(activity, to, actor, payload)` using table; emits `DomainEvent(kind, owner, entity, before, after)` onto an in-process event bus (M08 subscribes). Operations: start, extend(+min), delay(new_eta), change, arrive, cancel, complete, expire.
5. **Defaults by type:** default durations (study 60, meal 30, meeting 60, gym 60, nap 30, social 90, personal 60, custom 60); sleep ends at routine wake. Expected end always set.
6. `GET /state/me` (ResolvedState) and `GET /state/{owner_id}` (ViewerState via visibility.project). `GET /timeline?date=` returns ordered segments for the day (owner) and `GET /timeline/{owner_id}` (viewer-projected, status level minimum).

## Edge cases to test
Overlapping templates (most specific / latest start wins, log conflict); cross-midnight sleep; DST-free but tz-aware; day with exam AND manual study; extended class pushes free window; cancelled class creates immediate free segment; trip ETA before now; clock jump (DemoClock); empty user (Unknown layer, not an error).

## Tests: fixtures for the 5 demo workflows; property test that resolver never returns an expired manual activity; snapshot test for timeline day.
## DoD: resolver + expand fully unit-tested, no I/O inside. Update MEMORY.md.
