# M05: Cards (thin typed layers over the engine)
**Depends on:** M04. **Rule:** no per-card engine. A `CardSpec` registry only.

## Build
1. `cards/registry.py`: `CardSpec{key, activity_types, meta_model, defaults, lifecycle, notification_kinds, grant_card}`; generic routes `POST/PATCH/GET /cards/{key}` plus friendly aliases below.
2. **Schedule:** CRUD for weekly slots (class, lab, break, lunch, free, other) with week_pattern, bulk save for whole timetable, exceptions endpoints (`POST /schedule/exceptions` cancel/extend/early_end/move/day_off), "free earlier" = early_end. Derived states come from resolver.
3. **Exam:** `exam_sets` per date (multiple exams + breaks with `calls_ok`), buffers, season overview `GET /exam/season` (grouped by date, counts, two-exam days).
4. **Live Activity:** start/extend/end/change; quick chips; custom activity (icon, label); fields: start, expected end, availability, message, visibility (inherit | private_label | only viewers).
5. **Travel:** create trip (destination+kind, depart, ETA, mode, companions [linked user or free text], vehicle number, driver name/phone as details-level, route), actions: depart, delay(new_eta), plan_changed, arrive, cancel; "return trip" prefill; `check_on_me` options; `expected_offline_window`. Starting a trip starts `ArrivalWatchWorkflow` via M08 interface (stub now).
6. **Phone & availability:** single `phone_state` doc: mode, calls, messages, battery, may_go_offline, declared_offline, until. On may_go_offline or battery critical, freeze `last_shared_context` snapshot from the current ResolvedState shareable fields and timestamp it (provenance user_shared). Battery buckets: ok >20, low <=20, critical <=10, dying <=5.
7. **Message Drop:** templates list, create (standalone or attached to activity), audience, expiry, quick reactions, optional `promise_at`.
8. **Safety-lite:** check-on-me lives on Travel; "Share context now" packet is P1 (stub endpoint returning 501 with TODO).
9. Each write: validate -> persist (version check) -> lifecycle event -> bus. Writes by owner only.

## Edge cases
Editing an active trip creates CHANGED not a new trip; companion linked to a connection is notified-eligible only if that companion granted anything (never auto-share the companion's info); vehicle/driver strictly details-level; private_label applies at projection.
## Tests: each card end-to-end through resolver and visibility; lifecycle invalid transitions rejected.
## DoD: all card endpoints work with seeded data. Update MEMORY.md.
