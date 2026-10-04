# MEMORY.md: Project memory (source of truth; agent updates Build Status + Decision Log)

## 1. Mission (one sentence)
`CircleCue`: a private, permission-based activity and life-context network so trusted people know what matters (free? busy? travelling? phone dying?) without repeatedly calling or asking. Built for a real person for Hacktoberfest 2026 "Build for a Friend". Deadline: Mon Oct 5 06:59 UTC.

## 2. Locked product rules
- Every user is equal. No parent/friend modes. Relationship = preset + permissions only.
- Connection is mutual; visibility is directional and per-card. New connection = zero access.
- Not a social feed. No likes, followers, chatbot, default location tracking, hidden monitoring.
- Distinguish provenance: user_shared | ai_parsed_user_confirmed | system_inferred | system_collected.
- AI is core: parsing, extraction, missing-info, significance judging, summaries. AI never authorizes, never does date math, never persists without user confirm.
- Not an emergency service.

## 3. Locked stack
Next.js+TS+Tailwind PWA (Render) | FastAPI+Pydantic v2+PyMongo async (Render) | MongoDB Atlas | Temporal (Cloud preferred; worker on Render) | Gemma via OpenAI-compatible endpoint on DigitalOcean GPU Droplet (vLLM or Ollama); Ollama local for dev | Sentry | TabPFN (P1) | Tinker (P2).
API is called same-origin via Next.js rewrites (`/api/*` -> API service) to avoid cross-site cookie problems. Realtime = SSE.

## 4. Repo layout (do not restructure)
```
/AGENTS.md
/apps/web                 Next.js
/apps/api/app
    main.py config.py clock.py
    core/        auth.py security.py errors.py audit.py ratelimit.py
    domain/      models.py lifecycle.py resolver.py visibility.py notifications.py scenarios.py freewindows.py
    cards/       registry.py schedule.py exam.py live.py travel.py phone.py message.py safety.py
    ai/          adapter.py providers/ schemas.py prompts/ parse.py timeparse.py people.py service.py evals/
    predict/     pickup.py
    workflows/   worker.py user_timeline.py arrival_watch.py promise.py activities.py
    routers/
/apps/api/tests
/infra/          render.yaml  do/ (gemma serving)  docker-compose.local.yml
/docs/           MEMORY.md DECISIONS.md PROPOSALS.md DEVLOG.md SMOKE.md ARCHITECTURE.md EVAL_REPORT.md SUBMISSION.md
/design/design.md   (user supplies)
/scripts/        seed_demo.py smoke.py seed_call_history.py
```

## 5. Core contracts

### 5.1 Collections (Mongo). Additive changes only.
`users` {_id, name, user_code, email, pw_hash, tz, avatar_url, routine_prefs{wake,sleep,min_call_window_min=10,buffer_min=5}, ai_prefs{store_raw=false}, sharing_paused{active,until}, created_at}
`connections` {_id, a, b, status: pending|active|blocked, requested_by, created_at}
`grants` {_id, owner, viewer, relationship_preset, cards{schedule,exam,live,travel,phone,safety,message: none|status|details}, notify{free_now,exam,travel,battery,schedule_change,message,safety: bool}, important: bool, reach_through: bool, expires_at, revoked_at, created_at}
`share_links` {_id, code, owner, scope{card|activity_id}, expires_at, max_uses, uses, revoked_at}   (P1)
`templates` {_id, owner, kind: SCHEDULE_SLOT|ROUTINE|SCENARIO_TIME, title, activity_type, days[], start_local, end_local, week_pattern: every|A|B, availability{calls,messages}, visibility, active_from, active_to, version=1}
`exceptions` {_id, owner, template_id|null, date, kind: cancelled|moved|extended|early_end|day_off, new_start, new_end, note, version=1}
`exam_sets` {_id, owner, date, items[{type: exam|break, subject?, start_local, end_local, calls_ok?}], pre_buffer_min=30, post_buffer_min=15, keep_schedule=false, version=1}
`activities` {_id, owner, type, title, status, phase?, start_at, expected_end_at, availability{calls,messages}, metadata{}, visibility{mode: inherit|private_label|only, label_override, viewer_ids[]}, participants[], provenance{source, model?, confidence?, confirmed_at?}, check_on_me?{enabled, grace_min, escalate_min}, version, created_at, updated_at}
`phone_state` {_id=owner, mode, calls, messages, battery_pct, battery_bucket, may_go_offline, declared_offline, until, last_shared_context{snapshot, shared_at}, updated_at, version=1}
`messages` {_id, owner, text, template_key, activity_id?, audience[], expires_at, promise_at?, promise_done_at?, reactions[], version=1}
`scenarios` {_id, owner, name, enabled, source{kind, raw_text?, model?}, trigger, conditions[], effects[], audience, notification_rule, priority, last_fired_at}
`connection_plans` {_id, owner, target, importance, rule, preferred_window, last_connected_at, snoozed_until, cooldown_min, nudges_today}
`call_events` {_id, caller, callee, ts, outcome: picked|missed, features{...}, synthetic: bool}   (P1)
`notifications` {_id, to, about_owner, kind, payload_redacted, action, dedupe_key, status, created_at, delivered_at, read_at}
`audit_log` {_id, actor, action, target, meta, at}
`ai_invocations` {_id, user, task, model, latency_ms, schema_valid, repaired, confirmed, error?, at}  (no raw text unless ai_prefs.store_raw)
Indexes: users.user_code unique; grants(owner,viewer) unique; notifications(to, created_at), dedupe_key unique-sparse; activities(owner, status, expected_end_at); templates(owner); call_events(caller,callee,ts).

### 5.2 Layer precedence (resolver, highest wins) for ACTIVITY
1 Safety/active context packet -> 2 manual Live Activity/availability override (unexpired) -> 3 active Travel -> 4 Exam (date set) -> 5 Scenario-produced activity -> 6 Schedule (with exceptions) -> 7 Routine baseline -> 8 Unknown. Within a layer, newest explicit wins.
REACHABILITY merge: unexpired manual override wins; else most restrictive among active layers; else routine default. Phone state is a separate axis (battery, silent, offline).
Expired manual activity: status EXPIRED, resolver ignores it, owner prompted to extend.

### 5.3 ResolvedState (owner side) and ViewerState (after visibility.project)
```
ResolvedState {owner, as_of, activity{type,label,until,layer,provenance}, reachability{calls: ok|prefer_not|no, messages: ok|later, reason, until, free_in_min?},
 phone{mode,battery_bucket,may_go_offline,declared_offline,stale}, travel?{destination,eta,phase,overdue,companions,vehicle?,mode},
 exam?{state,subject,until,next_free_window?,exams_today}, last_shared_context?{snapshot,shared_at}, next_boundary_at, sharing_paused}
ViewerState = same fields, redacted by grant level (status vs details), private-label applied, nulls where not granted.
```

### 5.4 Lifecycle (data-driven table in lifecycle.py)
Generic: PLANNED -> ACTIVE -> (EXTENDED|DELAYED|CHANGED)* -> COMPLETED | CANCELLED | EXPIRED. Travel `phase`: planned, travelling, delayed, arrived, completed. Transitions validated by table; each transition emits an event for the notification pipeline.

### 5.5 Notification pipeline (single path)
event -> candidate viewers (active connection + grant allows card + notify flag + not paused) -> significance (deterministic table; AI judge only for custom/free-text) -> dedupe -> rate limit -> viewer quiet hours (safety kinds bypass) -> render text from REDACTED projection (templates) -> suggested action (CALL | MESSAGE | REMIND_LATER | NONE) -> persist -> re-check grant -> deliver (SSE; web push P1).
Kinds: FREE_NOW, EXAM_STARTED, EXAM_BREAK, EXAM_FINISHED, CLASS_CANCELLED, SCHEDULE_CHANGED, ACTIVITY_STARTED, ACTIVITY_EXTENDED, TRAVEL_STARTED, TRAVEL_DELAYED, PLAN_CHANGED, TRAVEL_ARRIVED, BATTERY_LOW, BATTERY_CRITICAL, PHONE_MAY_GO_OFFLINE, MESSAGE_DROP, ARRIVAL_MISSING, ALL_CLEAR, PROMISE_DUE, URGENT_OVERRIDE, CONNECTION_REMINDER (owner-only).
Never notify: normal continuation, edits within 5 min, duplicates.

### 5.6 AI contract
`POST /ai/parse {text, mode, client_now, tz}` -> `ParseResult{intent, language, items[], missing[{field,question}], confidence, notes}`. Nothing persisted. `POST /ai/confirm {draft_ids|edited items}` persists with provenance. Time uses `TimeSpec{hh_mm, date_ref: today|tomorrow|YYYY-MM-DD|weekday:XXX, relative_min, ampm_assumed}`; code resolves to UTC. Companion names matched by code against owner's connections; ambiguous -> ask.
Provider ladder: primary (DO Gemma) -> secondary (local Ollama) -> rules parser -> form fallback. Timeout 8 s, one repair retry.
Model context sent: owner's own text, tz, now, first names of owner's connections, titles of owner's templates. Nothing about other users' state.

### 5.7 Temporal workflows (P0)
- `UserTimelineWorkflow(user_id)`: long-running; computes `next_boundary_at` via resolver, waits (timer or `timeline_changed` signal), runs activity `emit_transition`, continue-as-new daily.
- `ArrivalWatchWorkflow(activity_id)`: signals delay/arrived/cancel/plan_changed; timers at ETA+grace (nudge owner) and +escalate (notify viewers).
- `PromiseWorkflow(message_id)` [P1].
All activities idempotent via dedupe keys. Workflow code deterministic.

## 6. Defaults
min call window 10 min | buffer 5 | delay notify >=10 min | grace 15 + escalate 15 | message expiry 12 h | context packet 6 h | AI timeout 8 s | nudges/day 2 | night-travel prompt after 21:00 | stale snapshot badge after 3 h.

## 7. Partner usage (honest)
Gemma on DO GPU = AI core. Render = hosting. Temporal = durable timers. Atlas = DB. Sentry = tracing. TabPFN = P1 pick-up predictor (features contain no PII; prefer local/DO if time). Tinker = P2 fine-tune with measured eval, must name the base model actually fine-tuned. Not used: ElevenLabs, Backboard, Mastra, SerpApi, Arduino.

## 8. Build Status (agent updates)
| Module | Tier | Status | Notes |
|---|---|---|---|
| M00 Scaffold | P0 | done | Scaffold project, FastAPI, Next.js, Docker, Sentry, Clock tests pass |
| M01 Data model | P0 | done | All 16 collections modelled, lifecycle transition table, AsyncMongoClient db.py, gen_types script |
| M02 Auth/profile/code | P0 | done | Register, login, universal code NAME-XXXX, profile, code lookup, pause, export, delete |
| M03 Connections+visibility | P0 | done | Directional grants, profile/state/timeline reads through `domain/visibility.py`, matching-owner/viewer checks, active-connection notification candidates, pause/revoke/private-label redaction; 25 tests pass |
| M04 Activity engine+resolver | P0 | done | Pure resolver, overnight template expansion, exceptions/exam states, free-window rules, lifecycle service, injected time, next-boundary and snapshot handling; state and owner/viewer timeline routes; 40+ focused tests pass |
| M05 Cards | P0 | done | CardSpec registry and generic owner CRUD over existing collections; bulk schedules/exceptions, exam season, live/travel lifecycle and return prefill, phone snapshots/buckets, message templates/reactions, optimistic versions, card-family visibility tests; fixed web card reads to consume API arrays and schedule editor to use versioned bulk save; P1 context packet stub returns 501 (owner: M08) |
| M06 AI service | P0 | done | Typed drafts, verified OpenAI-compatible/Ollama structured-output adapters, rules fallback, timezone post-processing, connection-name matching, parse/confirm routes, Sentry span, privacy-safe invocation log, 60-case eval suite passes, live DO test stub |
| M07 Scenario engine | P0 | done | Typed DSL, time-trigger resolver layer 5, versioned CRUD/dry-run, grant-intersected audience preview, AI confirmation, activity_state and battery event triggers wired into notifications pipeline, 6 scenario integration tests pass |
| M08 Notifications+Temporal | P0 | done | Complete notification pipeline, ArrivalWatchWorkflow (grace, nudge, escalate, all-clear), UserTimelineWorkflow, PromiseWorkflow, Temporal test environment with time skipping, /dev/tick clock jump, Sentry workflow tagging, 139 tests pass |
| M09 Reminders (+TabPFN) | P0 basic / P1 | done | Connection reminder evaluation (cadence rules, 2/day cap, 4h cooldown, snooze, dedupe); PickupPredictor heuristic stub + TabPFN adapter stub; REST API /reminders/plans + /check + /predict/pickup; 5 tests pass |
| M10 Frontend | P0 | done | Complete Next.js PWA with Apple-style design tokens, auth, dashboard, AI quick compose sheet, people circle + state viewer, alerts + grant permissions editor, schedule, exam, travel with Arrival Watch, messages, and profile management; corrected schedule/exam array handling, schedule persistence, exam editing, quick-update missing-answer flow, and visible card errors; production build passes |
| M11 Observability+hardening | P0 | done | Rate limiter tests, X-Frame-Options/nosniff/strict-referrer security headers middleware, HTML text sanitization, Sentry error endpoint |
| M12 Deploy | P0 | done | render.yaml blueprint (web, api, worker), docker-compose.local.yml with Mongo/Temporal/Ollama, complete .env.example with DO GPU / Atlas configuration |
| M13 Tinker | P2 | todo | |
| M14 Demo+docs+submission | P0 | done | seed_demo.py (httpx, 10-step seeder: Arjun+Priya+connection+grants+schedule+exam+travel+plan+phone), SMOKE.md M09 section, full SUBMISSION.md for Hacktoberfest 2026 |

## 9. Decision Log (append only)
- D1: Arrival Watch promoted to P0 (best Temporal fit, low cost).
- D2: Resolved-not-stored state; Temporal triggers only.
- D3: AI output is a draft; user confirms before persistence or sharing.
- D4: Same-origin API via Next.js rewrites; SSE for realtime.
- D5: Split hosting: Render = app tier, DigitalOcean = GPU model tier (distinct purposes).
- D6: Manual "connected" confirmation; no call-log access; no default location.
- D7: Time-based custom scenarios in P0; event-based in P1.
- D8: Switch component composed from tokens (pill track; on=primary, off=chip-translucent).
- D9: `--danger` (#d70015) allowed only for destructive/error text+icons.
- D10: MVP is light-dominant; no system dark mode; dark tiles are semantic (busy).
- D11: Mobile bottom tab bar reuses `floating-sticky-bar` styling.
- D12: Loading = parchment skeleton blocks (no shimmer gradient); empty = lead-airy sentence + one pill CTA.
- D13: The untyped `last_shared_context` packet is exposed only to an active viewer with `safety: details`; lower card grants cannot safely redact its arbitrary snapshot fields.
- D14: M05 adds `version=1` to mutable non-activity card documents so generic PATCH/DELETE operations can use optimistic concurrency without adding collections.
- D15: M08 ensures safety notifications (ARRIVAL_MISSING, ALL_CLEAR, URGENT_OVERRIDE) bypass viewer daily rate limits and quiet hours.
- D16: M08 implements /dev/tick endpoint for deterministic demo clock jumps and boundary triggers in non-production environments.
- D17: Card list routes return arrays; card editor pages consume that contract directly, schedule edits use the versioned bulk-save endpoint, and incomplete AI quick updates must be reparsed after answers before confirmation.
- Design: `design/DESIGN.md` provided by user (Apple-style). Availability maps to tile surface (light = reachable, dark = busy) always paired with text + icon.
