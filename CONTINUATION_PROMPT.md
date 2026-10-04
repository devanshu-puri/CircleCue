# CircleCue — Full Continuation Prompt
### Paste this ENTIRE message as your first message in the new Antigravity session

---

## CONTEXT: WHO YOU ARE AND WHAT THIS IS

You are continuing development of **CircleCue** — a private, permission-based activity and life-context network.  
**Hacktoberfest 2026 "Build for a Friend". Hard deadline: Mon Oct 5 06:59 UTC.**

**Before you write a single line of code:**
1. Read `AGENTS.md` fully — it is your law.
2. Read `docs/MEMORY.md` fully — it is the source of truth for build status.
3. Read `design/DESIGN.md` — all UI tokens must come from `design/tokens.css` only.

---

## STEP 0 — COMMIT EVERYTHING (DO THIS FIRST, RIGHT NOW)

M04 through M08 are fully implemented on disk but **NOT committed**. Run this immediately:

```bash
cd apps/api && python -m pytest tests/ -x -q
```

If tests pass (expect ~200 passing), commit:

```bash
git add -A
git commit -m "feat(M04-M08): resolver, cards, AI service, scenarios, notifications, Temporal workflows"
```

If any tests fail, fix them before committing — do NOT skip. The test files already exist on disk at `apps/api/tests/`.

---

## STEP 1 — FINISH M06: AI SERVICE (eval + live model verification)

**Status:** All code is written. Two things are missing.

### 1a. Run the 60-case eval suite

The AI service is at `apps/api/app/ai/service.py`. The adapter ladder is: DO Gemma (OpenAI-compat) → local Ollama → RulesProvider fallback.

Create `apps/api/tests/evals/test_parse_eval.py` with these 60 cases (table-driven with `@pytest.mark.parametrize`):

**Category A — Schedule (15 cases):**
- "class from 9 to 11" → intent=schedule, start=09:00, end=11:00, no missing
- "lecture tomorrow 2pm till 4" → date_ref=tomorrow, start=14:00, end=16:00
- "cancel monday class" → intent=exception, kind=cancelled, weekday:MON
- "move friday lecture to saturday 10am" → intent=exception, kind=moved, new_start=10:00
- "study session every mon wed fri 8pm to 10pm" → intent=schedule, days=[0,2,4]
- "no class next week" → intent=exception, kind=day_off, date_ref=next week
- "extend today's session by 30 min" → intent=exception, kind=extended
- "class starts at 9 not 10 from next week" → intent=schedule update
- "week A pattern lecture tue thu" → week_pattern=A, days=[1,3]
- "add buffer after lecture don't call me for 15 mins after" → buffer_min=15
- "office hours 3-4:30 pm" → start=15:00, end=16:30
- "seminar every other friday" → week_pattern=B, days=[4]
- "lab session ends at 17:30" → end=17:30
- "my morning routine is 7am to 9am" → kind=ROUTINE
- "clear all monday entries" → intent=exception, kind=cancelled, day=all mondays

**Category B — Exam (10 cases):**
- "exam season starts oct 12" → intent=exam_season, date=oct 12
- "physics exam 2pm to 5pm with 30min break at 3:30" → items with break
- "exam tomorrow 9am don't call" → calls=no
- "finals week mon to fri" → exam_set with range
- "chem exam done" → intent=exam_complete
- "add 15 min pre-buffer before tomorrow's exam" → pre_buffer_min=15
- "math test 10:30" → missing=[end]
- "paper tomorrow morning" → missing=[start, end]
- "break at 3pm for 15 min" → kind=break, start=15:00, end=15:15
- "no exams today" → intent=no_exam

**Category C — Travel (10 cases):**
- "leaving for Delhi tomorrow at 8am arriving 6pm" → travel, depart tomorrow 08:00, eta 18:00
- "flight at 14:30 landing 19:00" → depart=14:30, eta=19:00
- "going with Rahul" → companion=Rahul, ambiguous if multiple Rahuls
- "train delayed by 2 hours" → intent=travel_delay, elapsed_min=120
- "reached home" → intent=travel_arrived
- "night travel — be back by morning" → may_go_offline=true
- "going to Mumbai for 3 days" → destination=Mumbai, duration=3 days
- "on the way, eta 30 min" → relative_eta=30min
- "car trip with family" → participants=family (ask for names)
- "trip cancelled" → intent=travel_cancel

**Category D — Phone/battery (5 cases):**
- "phone dying, going offline" → mode=dnd, may_go_offline=true
- "battery 8%" → battery_pct=8, battery_bucket=critical
- "on silent till 9pm" → mode=silent, until=21:00
- "charging now" → battery recovery signal
- "won't be reachable for an hour" → until=+60min

**Category E — Message (5 cases):**
- "tell everyone I'll be free at 5" → intent=message, audience=all, text=...
- "message Priya I'm on my way" → audience=[Priya]
- "drop a note: I might be late" → intent=message
- "remind me to call mom at 8pm" → intent=reminder, due=20:00
- "promise to reply by tomorrow noon" → intent=promise, promise_at=tomorrow 12:00

**Category F — Edge cases (15 cases):**
- empty string → confidence=0, intent=unknown, missing=[text]
- "ok" → confidence=low, intent=unknown
- gibberish → rules fallback, confidence=0
- ambiguous time "morning" → ampm_assumed=true, missing=[exact_time]
- "2 hours from now" → relative_min=120
- mixed language (Hindi+English) → language=hi-en, parse best effort
- "8" (just a number) → missing=[intent, time_unit]
- multiple intents in one message → items array with two entries
- date "5th" with no month → date_ref ambiguous, ask for month if not deterministic
- "busy for a while" → confidence=low, availability=prefer_not
- past date reference → warn, do not persist
- "don't share this with anyone" → visibility.mode=private_label
- "only Priya can see" → visibility.mode=only, viewer_ids=[Priya]
- "call me any time" → availability.calls=ok
- "don't disturb" → availability.calls=no, availability.messages=later

**Eval scoring:** Each case asserts `intent`, `missing` fields (present or absent), and key `items[0]` fields. Confidence threshold: ≥ 0.6 for clear cases. RulesProvider must handle at least categories D and F edge cases without any LLM.

### 1b. Verify live DO Gemma endpoint

Add `apps/api/tests/test_ai_live.py` (skip unless `AI_PROVIDER=openai_compat` env is set):

```python
import os, pytest
pytestmark = pytest.mark.skipif(
    os.getenv("AI_PROVIDER") != "openai_compat",
    reason="Live model test requires AI_PROVIDER=openai_compat"
)

async def test_live_parse_simple(ai_service):
    outcome = await ai_service.parse("class at 9am to 11am", "schedule", now, "Asia/Kolkata", [])
    assert outcome.schema_valid
    assert outcome.result.intent == "schedule"
    assert outcome.provider != "rules"  # must use real model
```

Run it locally with the DO endpoint env vars from `.env.example`.  
Update MEMORY.md: M06 status → **done**.  
Commit: `git commit -m "feat(M06): 60-case eval suite, live model verification, M06 complete"`

---

## STEP 2 — FINISH M07: SCENARIO ENGINE (event triggers)

**Status:** Time-trigger scenarios work. Event triggers (`activity_state`, `battery`) are modelled in `domain/scenarios.py` but NOT wired into the notification pipeline.

### 2a. Wire ActivityStateTrigger into the pipeline

In `apps/api/app/domain/notifications.py`, in the `publish_and_process` function (already exists), add handling for `ACTIVITY_STARTED` and `ACTIVITY_EXTENDED` events:

After the existing notification logic runs for an event, check if any enabled scenario has `trigger.kind == "activity_state"` and its `activity_type` matches the event's activity type. If so:
1. Load the owner's scenarios from DB: `db.scenarios.find({"owner": owner_id, "enabled": True})`
2. For each matching `ActivityStateTrigger` scenario, check `elapsed_min` ≤ time since activity started.
3. If conditions pass, apply `SetActivityEffect` by inserting into `activities` collection with `provenance.source = "system_inferred"`, then fire a `SCENARIO_CHANGED` domain event so Temporal picks it up.

### 2b. Wire BatteryTrigger

When `BATTERY_LOW` or `BATTERY_CRITICAL` events fire, check for scenarios with `trigger.kind == "battery"` where `trigger.threshold_pct >= current_battery_pct`. Apply effects same way as above.

### 2c. Add scenario integration tests

In `apps/api/tests/test_scenarios.py` (already exists), add:
- `test_activity_state_trigger_fires_on_activity_started`
- `test_battery_trigger_fires_at_threshold`
- `test_scenario_audience_intersects_grants` (already should exist, verify it does)

Update MEMORY.md: M07 status → **done**.  
Commit: `git commit -m "feat(M07): activity_state and battery event triggers, M07 complete"`

---

## STEP 3 — BUILD M10: FRONTEND (biggest chunk — plan carefully)

**Current state:** There are skeleton pages at `apps/web/app/{page.tsx, people/page.tsx, permissions/page.tsx, design-check/page.tsx}`. The component library is at `apps/web/components/ui.tsx` (Tile, PillButton, Chip, Switch, SearchInput, Footer, ProvenanceCapsule, GlobalNav, SubNavFrosted). The API client is at `apps/web/lib/api.ts`.

**Design rules (absolute):**
- Every color, radius, and font MUST use a CSS token from `design/tokens.css` (e.g., `var(--primary)`, `var(--canvas)`, `var(--r-lg)`). Never hard-code a hex.
- Availability maps: light tile = reachable, dark tile = busy. Always paired with text + icon.
- Pill shape for action buttons. Press = `scale(0.95)`. Min tap target 44px.
- Body text 17px. No weight 500. No shadows except `.product-shadow` on photos. No gradients.
- `--danger` (#d70015) only for destructive/error text+icons.

**Build these pages in this order:**

### 3a. Auth pages: `/login` and `/register`

Create `apps/web/app/login/page.tsx` and `apps/web/app/register/page.tsx`.

**Login page:**
- Single card (Tile tone="parchment"), centered.
- Fields: email, password (both 44px min-height inputs using token borders).
- "Sign in" PillButton (full width, variant=primary).
- Link to `/register`.
- On submit: `POST /api/auth/login` with `{email, password}`. On 200: store JWT in httpOnly cookie (handled server-side — the API sets `Set-Cookie`). Redirect to `/`.
- On error: show error in `--danger` color text below the form.
- No hard-coded colors.

**Register page:**
- Fields: name, email, password, timezone (use `Intl.DateTimeFormat().resolvedOptions().timeZone` as default).
- "Create account" PillButton.
- On submit: `POST /api/auth/register`. On 201: redirect to `/login`.

**API client additions needed in `apps/web/lib/api.ts`:**
```typescript
export async function login(email: string, password: string): Promise<void>
export async function register(name: string, email: string, password: string, tz: string): Promise<void>
export async function logout(): Promise<void>
```

### 3b. Home / Dashboard (`/`) — enhance existing

The home page exists but uses hardcoded mock chips. Make it functional:

1. `getMyState()` already calls `GET /api/state/me` — verify this returns `ViewerState` with the correct shape per `domain/models.py`: `{activity, reachability, phone, travel, exam, next_boundary_at, sharing_paused}`.
2. The dark Tile (tone="dark") at top shows current status. Map it correctly:
   - If `state.reachability.calls === "ok"`: tile tone="light" (reachable)
   - If `state.reachability.calls === "prefer_not"` or `"no"`: tile tone="dark" (busy)
   - Show `state.activity.label` or `state.activity.type` as the headline.
   - Show `reachability.reason` as subtext.
   - Show `reachability.free_in_min` as "Free in X min" if present.
3. The SearchInput opens the AI Quick Compose flow (see 3e).
4. The 4-card grid (Schedule, Exam, Travel, Phone) links to respective card pages (build those in 3f).
5. The "Today" section shows real `next_boundary_at` formatted as local time.
6. The Alerts count in GlobalNav comes from `notifications.length` (already wired, make badge dynamic).
7. Bottom nav tab bar already exists; keep it. The 4 tabs are: Home (`/`), People (`/people`), Alerts (`/alerts`), Me (`/me`).

### 3c. AI Quick Compose — modal/sheet

When the user taps the SearchInput on the home page, open a bottom sheet (slide up) with:

1. A large textarea (17px, no border, placeholder "What's happening? Tell me in plain words…").
2. "Parse" PillButton (variant=primary). On tap:
   - Call `POST /api/ai/parse` with `{text, mode: "auto", client_now: new Date().toISOString(), tz: Intl.DateTimeFormat().resolvedOptions().timeZone}`.
   - Show a loading skeleton (parchment block, no shimmer).
   - On response: show the parsed draft as a confirmation card.
3. If `result.missing.length > 0`: show each `missing[i].question` as a follow-up input row (inline, not a new page).
4. "Confirm" PillButton: call `POST /api/ai/confirm {draft_ids: [...] | edited items}`.
5. "Edit manually" link: expand the full form inline.
6. ProvenanceCapsule shows "AI parsed · confirm to save".

Add to `apps/web/lib/api.ts`:
```typescript
export async function parseText(text: string, mode: string): Promise<ParseResult>
export async function confirmDraft(items: unknown[]): Promise<void>
```

### 3d. People page (`/people`) — enhance existing

`apps/web/app/people/page.tsx` currently exists as a skeleton.

**Layout:**
- SubNavFrosted title="People" + PillButton "Add" (variant=ghost).
- Section: "Connections" — list from `GET /api/connections` (returns array of `{_id, other_user: {name, user_code, avatar_url}, status, grant?}`).
  - Each row: avatar circle (initials fallback), name, user_code, availability tile tone based on their state.
  - Tap → viewer state detail sheet (see below).
- Section: "Pending" — connections with `status: "pending"` have "Accept" + "Decline" pills.
- "Add person" flow: SearchInput → search by `GET /api/users/lookup?code=NAME-XXXX` → show profile card → "Connect" PillButton → `POST /api/connections`.

**Viewer state detail sheet:**
- Slides up on connection tap.
- Calls `GET /api/state/{user_id}` (viewer route) — shows their ViewerState.
- Shows: current activity tile (tone based on reachability), phone state, travel state, exam state.
- ProvenanceCapsule for each field that has provenance.
- "Call" and "Message" PillButtons (these are cosmetic for MVP — just `tel:` and `sms:` links).

Add to `apps/web/lib/api.ts`:
```typescript
export async function getConnections(): Promise<Connection[]>
export async function lookupUser(code: string): Promise<UserProfile>
export async function sendConnectionRequest(targetId: string): Promise<void>
export async function respondToConnection(connectionId: string, accept: boolean): Promise<void>
export async function getViewerState(userId: string): Promise<ViewerState>
```

### 3e. Permissions/Alerts page (`/permissions`) — rename to `/alerts` and add grants

The current `/permissions` page is a skeleton. Build two sub-tabs:

**Tab 1: Alerts** (rename current permissions page or add `/alerts`)
- List from `GET /api/notifications` (returns `NotificationItem[]`).
- Each notification row: kind icon (emoji fallback), text, timestamp relative ("2 min ago").
- Tap to mark read: `PATCH /api/notifications/{id}/read`.
- SSE stream already set up in `subscribeToNotifications` in `lib/api.ts` — connect it here too.
- Empty state: "No new alerts" in `--ink-muted-48` text + one pill CTA.

**Tab 2: Permissions** (what each person can see about you)
- List connections. For each: their name + a summary of their grant.
- Tap → grant editor sheet:
  - For each card (Schedule, Exam, Live, Travel, Phone, Message, Safety): segmented control with options [None, Status, Details].
  - Notify toggles (Switch component) for each notify flag.
  - "Important" toggle (reach-through).
  - "Save" PillButton → `PUT /api/grants/{connection_id}`.
  - "Revoke all" link in `--danger` color.

Add to `apps/web/lib/api.ts`:
```typescript
export async function getNotifications(): Promise<NotificationItem[]>  // already exists, verify shape
export async function markNotificationRead(id: string): Promise<void>
export async function getGrant(connectionId: string): Promise<Grant>
export async function updateGrant(connectionId: string, grant: GrantUpdate): Promise<void>
```

### 3f. Card pages (Me section at `/me`)

Create `apps/web/app/me/page.tsx` — this is the owner's card editing hub.

**Layout:**
- SubNavFrosted title="Me" + PillButton "Pause sharing" (variant=ghost, calls `POST /api/users/me/pause`).
- Section cards in a vertical list, each is a Tile (tone="parchment") with:

**Schedule card** → opens `/me/schedule`:
- List templates from `GET /api/cards/schedule`.
- Each template: title, days, start_local–end_local, availability chips.
- "Add slot" PillButton → opens Quick Compose (AI parse mode=schedule) or manual form.
- Manual form fields: title, days (multi-select chips), start/end time inputs, week pattern (A/B/Every chips), availability switches.
- "Save" → `POST /api/cards/schedule` (bulk).

**Exam card** → opens `/me/exam`:
- Show active exam set if any: `GET /api/cards/exam`.
- "Add exam session": date, start, end, subject, calls_ok switch.
- "Add break": start, end.
- Pre/post buffer inputs.
- "Finish exam season" PillButton → `DELETE /api/cards/exam/{id}`.

**Live activity card** → inline on `/me`:
- Quick add: tap "What are you doing?" → AI Quick Compose (mode=live).
- Shows current active activity with lifecycle controls: "Extend", "Wrap up", "Cancel".
- Extend → modal with new end time input → `PATCH /api/cards/live/{id}`.
- Wrap up → `PATCH /api/cards/live/{id}` with `status=COMPLETED`.

**Travel card** → opens `/me/travel`:
- Active travel if any: destination, ETA, phase badge, companion name.
- "Start travel" → AI Quick Compose (mode=travel) or manual form.
- Manual form: destination, depart time, ETA, vehicle type chips, companion picker (from connections), night travel toggle.
- Lifecycle controls: "Delay", "Arrived", "Cancel".

**Phone card** → inline on `/me`:
- Battery % display (if shared).
- Mode toggles: Normal / Silent / DND (Switch components).
- "May go offline" toggle.
- "Share update" PillButton → `POST /api/cards/phone`.

**Message card** → opens `/me/messages`:
- List active messages: `GET /api/cards/message`.
- "Drop a note" → AI Quick Compose (mode=message).
- Message row shows: text, audience names, expires_at countdown.
- "Promise" badge if `promise_at` is set.

### 3g. Me profile page (`/me/profile`)

- `GET /api/users/me` → shows name, user_code (large, copyable), avatar.
- User code: display as pill with copy button. Tapping copies to clipboard.
- Routine prefs: wake time, sleep time, call window min inputs.
- "Export my data" link → `GET /api/users/me/export`.
- "Delete account" in `--danger` → `DELETE /api/users/me` with confirmation modal.
- "Pause all sharing" big switch at top.

### 3h. Notifications SSE — make it persistent

In `apps/web/app/layout.tsx`, add a global SSE hook that:
1. On mount, opens `EventSource('/api/notifications/stream')`.
2. On message: updates a global notification count (use React context or Zustand if already installed, else useState in layout).
3. The GlobalNav component should accept `alertCount: number` as a prop and render the badge dynamically.
4. On 401 (SSE closes with error): redirect to `/login`.

### 3i. Auth guard

Add `apps/web/lib/auth.ts`:
```typescript
export function useRequireAuth(): void  // redirects to /login if no session
export function getSession(): Promise<{userId: string} | null>
```

Every page except `/login` and `/register` should call `useRequireAuth()` at the top.

**After all M10 pages are built:**
- Run `cd apps/web && npm run build` — must complete with zero TypeScript errors.
- Update MEMORY.md: M10 status → **done**.
- Commit: `git commit -m "feat(M10): full frontend — auth, dashboard, AI compose, people, permissions, all card pages"`

---

## STEP 4 — M11: OBSERVABILITY + HARDENING

**Goal:** Verify all security and rate-limit requirements are actually enforced end-to-end.

### 4a. Rate limit verification

File: `apps/api/app/core/ratelimit.py` (already exists). Verify these limits are applied to the correct routes in `apps/api/app/main.py`:
- Auth (`/auth/login`, `/auth/register`): 10 req/min per IP
- Code lookup (`/users/lookup`): 20 req/min per user
- AI parse (`/ai/parse`): 5 req/min per user
- Urgent override (`/notifications/urgent`): 3 req/min per user

For each limit, add a test in `apps/api/tests/test_ratelimit.py`:
```python
async def test_ai_parse_rate_limit(client, auth_headers):
    for _ in range(5):
        r = await client.post("/ai/parse", ..., headers=auth_headers)
        assert r.status_code == 200
    r = await client.post("/ai/parse", ..., headers=auth_headers)
    assert r.status_code == 429
```

### 4b. Sentry forced-error test

For each backend module, add one `sentry_sdk.capture_message("TEST_ERROR_<MODULE>", level="error")` call in a `POST /dev/test-error` endpoint (already in `routers/dev.py` if it exists, else add it) that is disabled in production (`if settings.ENV != "production"`).

### 4c. Security header check

In `apps/api/app/main.py`, add middleware:
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
```

And add these response headers via middleware:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

### 4d. Text sanitization

In `apps/api/app/core/errors.py` or a new `apps/api/app/core/sanitize.py`, add:
```python
def sanitize_user_text(text: str, max_len: int = 500) -> str:
    """Strip HTML tags, truncate, normalize whitespace."""
```

Apply it to: activity `title`, message `text`, scenario `name`, template `title` — anywhere free-text from one user can be displayed to another. Add test.

### 4e. JWT cookie check

Verify in `apps/api/app/core/security.py` that the JWT is set with `httponly=True, secure=True, samesite="strict"`. If not, fix it.

Update MEMORY.md: M11 status → **done**.  
Commit: `git commit -m "feat(M11): rate limit tests, security headers, text sanitization, Sentry error test"`

---

## STEP 5 — M12: DEPLOY

### 5a. Finalize `infra/render.yaml`

The file exists. Verify or add these services:

```yaml
services:
  - type: web
    name: circlecue-web
    env: node
    buildCommand: cd apps/web && npm ci && npm run build
    startCommand: cd apps/web && npm start
    envVars:
      - key: NEXT_PUBLIC_API_URL
        value: https://circlecue-api.onrender.com

  - type: web
    name: circlecue-api
    env: python
    buildCommand: cd apps/api && pip install -r requirements.txt
    startCommand: cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: MONGODB_URI
        sync: false
      - key: JWT_SECRET
        sync: false
      - key: AI_BASE_URL
        sync: false
      - key: AI_API_KEY
        sync: false
      - key: TEMPORAL_ADDRESS
        sync: false
      - key: SENTRY_DSN
        sync: false

  - type: worker
    name: circlecue-worker
    env: python
    buildCommand: cd apps/api && pip install -r requirements.txt
    startCommand: cd apps/api && python -m app.workflows.worker
```

### 5b. DigitalOcean GPU Droplet (Gemma serving)

Check `infra/do/` directory for existing config. Verify `docker-compose.local.yml` has:
```yaml
ollama:
  image: ollama/ollama
  ports: ["11434:11434"]
  volumes: ["ollama:/root/.ollama"]
```

The Gemma model name must match what's in `.env.example` as `AI_MODEL`. Do NOT invent a model name — check `ollama list` or the DO GPU config. Mark with `TODO(verify): confirm model name on live DO droplet`.

### 5c. `.env.example` audit

Verify these vars exist in `.env.example` with placeholder values (no secrets):
```
MONGODB_URI=mongodb+srv://...
JWT_SECRET=changeme
AI_PROVIDER=openai_compat
AI_BASE_URL=https://your-do-gpu-droplet:8000/v1
AI_MODEL=gemma-3-4b-it  # TODO(verify): confirm on DO
AI_API_KEY=
TEMPORAL_ADDRESS=your-temporal-cloud:7233
TEMPORAL_NAMESPACE=default
SENTRY_DSN=https://...@sentry.io/...
ENV=development
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 5d. Docker smoke test

Run `docker compose -f infra/docker-compose.local.yml up -d` and verify API starts and returns 200 on `GET /health`.

Update MEMORY.md: M12 status → **done**.  
Commit: `git commit -m "feat(M12): render.yaml finalized, DO config, env audit"`

---

## STEP 6 — M09: REMINDERS (basic)

**Goal:** `CONNECTION_REMINDER` notifications nudge the owner to reach out to important connections.

The `NOTIFICATION_POLICIES` in `domain/notifications.py` already has:
```python
NotificationKind.CONNECTION_REMINDER: NotificationPolicy(None, AccessLevel.NONE, owner_only=True)
```

### 6a. Connection plan check

In `apps/api/app/workflows/user_timeline.py`, add to the daily `continue_as_new` loop:
1. Load `connection_plans` for the owner (`db.connection_plans.find({"owner": owner_id})`).
2. For each plan where `importance == "high"` and `last_connected_at` is older than `rule` (e.g., "3 days"), and `nudges_today < 2`:
   - Emit `CONNECTION_REMINDER` notification (owner only, not the connection).
   - Increment `nudges_today` in the plan document.
   - Reset `nudges_today` to 0 at midnight.

### 6b. Front-end nudge

On the People page (`/people`), if a connection has an unread `CONNECTION_REMINDER` notification, show a subtle indicator on their row (a small dot in `--primary` color — do NOT use any new color).

Update MEMORY.md: M09 status → **done (basic)**.  
Commit: `git commit -m "feat(M09): connection reminder nudges, 2/day max"`

---

## STEP 7 — M14: DEMO + DOCS + SUBMISSION (DEADLINE CRITICAL)

**This must be done before Oct 5 06:59 UTC.**

### 7a. Seed demo data

File `scripts/seed_demo.py` already exists. Make it runnable as:
```bash
python scripts/seed_demo.py --mongo-uri $MONGODB_URI
```

It must create two demo users with a full realistic dataset:
- **User A (owner):** Name "Arjun Kumar", code "ARJUN-7842", tz="Asia/Kolkata"
  - Schedule: Mon–Fri 9–11 "Algorithms lecture", Mon–Wed–Fri 14–16 "Lab", Thu 11–13 "Seminar"
  - Active exam set: "Algorithms final" Oct 7 10am–1pm, pre_buffer=30
  - Active travel: "Delhi" departing Oct 5 8am, ETA 6pm
  - Phone: battery_pct=23, mode=silent
  - Message: "In transit, reply later"
  - Scenario: "Late night study" — time trigger 22:00–02:00, calls=no

- **User B (viewer):** Name "Priya Singh", code "PRIYA-3391", tz="Asia/Kolkata"
  - Connected to Arjun (active connection)
  - Grant: schedule=details, exam=status, travel=details, phone=status, message=status, safety=status
  - notify: free_now=true, exam=true, travel=true, battery=true

Output a summary of what was created and the demo login credentials to stdout.

### 7b. Update SMOKE.md

`docs/SMOKE.md` exists. Add a manual smoke test checklist:
```
## Manual Smoke Test (5 minutes)

1. [ ] Register two accounts (Arjun, Priya) OR run `python scripts/seed_demo.py`
2. [ ] Login as Arjun. Home page shows current status tile (dark = busy if exam/lecture active).
3. [ ] Tap SearchInput. Type "lab session 2pm to 4pm". Parse → confirm.
4. [ ] Go to People → find Priya's code → Connect.
5. [ ] Login as Priya. People page shows Arjun with correct status.
6. [ ] As Arjun, update travel: "going to Delhi, back tomorrow evening". AI parses. Confirm.
7. [ ] As Priya, verify travel notification appears in Alerts.
8. [ ] As Arjun, open Permissions. Set Priya's exam card to "Details". Save.
9. [ ] As Priya, verify exam details visible on Arjun's profile.
10. [ ] As Arjun, set phone: battery 8%, mode DND. Priya gets BATTERY_CRITICAL notification.
11. [ ] As Arjun, pause all sharing. Priya's view goes blank.
12. [ ] As Arjun, delete account. Data gone.
```

### 7c. Complete SUBMISSION.md

`docs/SUBMISSION.md` exists (or create it). Fill in:
```markdown
# CircleCue — Hacktoberfest 2026 Submission

## What it does
One-sentence: CircleCue is a private, permission-based life-context network that lets trusted people know what matters — free? busy? traveling? phone dying? — without repeatedly calling or asking.

## How we built it
- Backend: Python 3.12 + FastAPI + Pydantic v2 + PyMongo async + Temporal Cloud
- Frontend: Next.js 14 App Router + TypeScript strict + Tailwind PWA
- AI: Gemma (open-weight) via vLLM on DigitalOcean GPU Droplet, OpenAI-compatible API
- DB: MongoDB Atlas (16 collections, pure resolver pattern — no stored state)
- Infra: Render (web + API + Temporal worker) + DigitalOcean GPU
- Monitoring: Sentry

## Challenges
- Pure resolver pattern: all state derived at read time from raw data, never stored computed state
- AI as a draft generator only: all persistence requires user confirmation
- Temporal for durable safety workflows: arrival watch with grace, nudge, escalate phases

## Try it
- Live URL: [your Render URL]
- Demo login: email=arjun@demo.com password=demo1234 (seeded by seed_demo.py)
- GitHub: https://github.com/[your-repo]/circlecue
```

### 7d. Final test run + commit

```bash
cd apps/api && python -m pytest tests/ -q
cd apps/web && npm run build
cd apps/api && python scripts/smoke.py  # if this script exists
```

All must pass. Then:
```bash
git add -A
git commit -m "feat(M14): seed_demo, SMOKE.md, SUBMISSION.md, all done"
git tag v1.0.0-hacktoberfest
git push origin main --tags
```

Update MEMORY.md: all modules done.

---

## ARCHITECTURE INVARIANTS — NEVER VIOLATE THESE

These are from AGENTS.md and must never be broken regardless of time pressure:

1. **One visibility choke point.** Every read of another user's data goes through `domain/visibility.py`. No router reads another user's DB documents directly.
2. **AI never persists.** `POST /ai/parse` returns a draft. Only `POST /ai/confirm` persists. Never call `db.insert` from AI code.
3. **State is resolved, not stored.** `domain/resolver.py` is a pure function `(user_data, now) → ResolvedState`. Never store computed state.
4. **Temporal only triggers.** Workflows decide WHEN. Resolver decides WHAT IS TRUE. Never put business logic inside a Temporal workflow — only call domain functions.
5. **Injected clock only.** Never call `datetime.now()` in domain code. Use the injected `Clock` from `app/clock.py`. In Temporal workflows use `workflow.now()`.
6. **Defaults private.** New connection = zero access. Scenarios can NEVER widen visibility beyond existing grants.
7. **Revocation immediate.** Re-check grants at read time AND just before notification delivery AND on SSE streams.
8. **Additive changes only.** Never rename collections, move top-level folders, or swap frameworks without a DECISION entry in `docs/DECISIONS.md` first.
9. **No hard-coded design values in frontend.** Every color must be `var(--token-name)`, every radius `var(--r-xxx)`, every font `var(--font-xxx)`.
10. **No secrets in repo.** All config via env. `.env.example` has only placeholders.

---

## FILE MAP (quick reference)

```
apps/api/app/
  main.py                    FastAPI app, routers registered here
  config.py                  Settings (pydantic-settings)
  clock.py                   Injected Clock (supports demo clock)
  db.py                      AsyncMongoClient, get_db()
  core/
    security.py              JWT auth, get_current_user_id()
    ratelimit.py             Rate limit decorators
    audit.py                 log_audit_event()
    errors.py                Typed exceptions
  domain/
    models.py                ALL Pydantic models (source of truth)
    visibility.py            ← ONE CHOKE POINT — all cross-user reads
    resolver.py              Pure resolver (user_data, now) → ResolvedState
    lifecycle.py             Transition table
    lifecycle_service.py     Lifecycle mutations
    notifications.py         Full notification pipeline + publish_and_process()
    scenarios.py             Typed DSL + resolve_time_scenarios()
    expander.py              Template overnight expansion
    freewindows.py           Free-window calculation
    events.py                DomainEvent types
  cards/
    registry.py              CardSpec registry
  ai/
    adapter.py               LLMProvider ABC + OpenAICompatProvider + OllamaProvider + RulesProvider
    service.py               AIService.parse() + .significance_judge()
    schemas.py               ParseResult, SignificanceResult, TimeSpec, Missing
    timeparse.py             resolve_time_spec() — deterministic time resolution
    people.py                match_person() — name→id matching
    missing.py               merge_required_missing()
    prompts/parse_v1.md      System prompt for parse
  routers/
    auth.py                  /auth/register, /auth/login, /auth/logout
    users.py                 /users/me, /users/lookup, /users/me/pause, export, delete
    connections.py           /connections CRUD
    grants.py                /grants CRUD
    state.py                 /state/me (owner), /state/{user_id} (viewer, through visibility.py)
    cards.py                 /cards/{card_type} CRUD (schedule, exam, live, travel, phone, message)
    ai.py                    /ai/parse, /ai/confirm
    notifications.py         /notifications, /notifications/stream (SSE), /notifications/{id}/read
    scenarios.py             /scenarios CRUD + /{id}/dry-run
    dev.py                   /dev/tick, /dev/test-error (non-production only)
  workflows/
    worker.py                Temporal worker entry point
    user_timeline.py         UserTimelineWorkflow
    arrival_watch.py         ArrivalWatchWorkflow
    promise.py               PromiseWorkflow
    activities.py            Temporal activities (DB calls, emit_transition)
    inputs.py                Workflow input dataclasses
    client.py                get_temporal_client()

apps/web/
  app/
    layout.tsx               Root layout, global SSE hook, auth guard
    globals.css              Imports design/tokens.css
    page.tsx                 Home dashboard
    login/page.tsx           Auth
    register/page.tsx        Auth
    people/page.tsx          Connections + viewer state
    permissions/page.tsx     Rename or extend to alerts + grants editor
    alerts/page.tsx          Notification list (new)
    me/page.tsx              Owner card hub
    me/schedule/page.tsx     Schedule editor
    me/exam/page.tsx         Exam season editor
    me/travel/page.tsx       Travel editor
    me/messages/page.tsx     Message editor
    me/profile/page.tsx      Profile + user code + data export
    design-check/page.tsx    Keep for design system verification
  components/
    ui.tsx                   GlobalNav, SubNavFrosted, Tile, PillButton, Chip,
                             Switch, UtilityCard, SearchInput, Footer, ProvenanceCapsule
                             (add: Sheet/BottomSheet, SegmentedControl, AvatarCircle)
  lib/
    api.ts                   All API calls (typed)
    auth.ts                  useRequireAuth, getSession
    types/api.ts             TypeScript types (generated from OpenAPI or hand-written)

design/
  DESIGN.md                  Visual design spec (source of truth for UI)
  tokens.css                 CSS custom properties — USE THESE ONLY
  APP_DESIGN_MAPPING.md      How design maps to code patterns

docs/
  MEMORY.md                  Build status — update after each module
  DECISIONS.md               Append-only decision log
  PROPOSALS.md               Ideas not in scope
  SMOKE.md                   Manual test checklist
  SUBMISSION.md              Hacktoberfest submission doc
  ARCHITECTURE.md            Architecture overview
```

---

## DONE CRITERIA

You are finished when:
- `cd apps/api && python -m pytest tests/ -q` → all green (200+ tests)
- `cd apps/web && npm run build` → zero TypeScript errors
- `python scripts/seed_demo.py` → creates two users, connection, grants, activities
- Manual smoke test in SMOKE.md passes end-to-end on the deployed Render URL
- MEMORY.md shows all M00–M14 as **done**
- Git has a clean commit for each module: `feat(Mxx): ...`
- `git tag v1.0.0-hacktoberfest && git push --tags`
- Hacktoberfest submission submitted at [platform URL] before Oct 5 06:59 UTC
