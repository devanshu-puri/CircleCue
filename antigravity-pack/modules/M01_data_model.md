# M01: Data model, schemas, indexes
**Goal:** the spine. Freeze contracts. **Depends on:** M00.

## Build
1. Pydantic v2 models in `domain/models.py` for every collection in MEMORY.md 5.1 (exact field names). Enums: ActivityType (CLASS, LAB, BREAK, LUNCH, FREE_PERIOD, EXAM, STUDY, SLEEP, WORK, MEETING, TRAVEL, MEAL, GYM, SOCIAL, FAMILY, BUSY, FREE, PERSONAL, PHONE_STATUS, SAFETY, CUSTOM), Status, TravelPhase, CardKey, AccessLevel(none|status|details), Calls(ok|prefer_not|no), Messages(ok|later), Provenance, NotificationKind.
2. `ResolvedState` and `ViewerState` models (MEMORY 5.3).
3. Mongo layer: `db.py` with PyMongo async client, repository classes (thin), `ensure_indexes()` at startup.
4. `lifecycle.py` skeleton: transition tables as data (dict), `can_transition(type, from, to)`.
5. Per-type `metadata` models (discriminated union): TravelMeta, StudyMeta, SleepMeta, CustomMeta, etc. Unknown/custom type uses CustomMeta{icon, label, extra: dict[str,str] limited}.
6. Export OpenAPI + generate TS types script `scripts/gen_types.sh` into `apps/web/lib/types`.

## Rules
- Every cross-user-visible string field has max length and sanitizer (strip control chars/HTML).
- IDs: ObjectId internally, string in API.
- All datetimes UTC aware; local times stored as "HH:MM" + owner tz.

## Tests
Model validation (bad enums, over-length), index creation idempotent, lifecycle table sanity.
## DoD: models import cleanly, indexes created, types generated. Update MEMORY.md (note any field you added; additive only).
