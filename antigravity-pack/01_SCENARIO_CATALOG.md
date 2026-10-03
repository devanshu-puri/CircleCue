# SCENARIO CATALOG (elaborated, optimized, with new major cases)

Legend: **[P0]** must ship, **[P1]** next, **[P2]** stretch, **NEW** = not in your original lists.
Principle: all scenarios below are **templates over ONE engine** (Activity + Template + Exception + Scenario rule + Notification pipeline). None get their own backend.

Every scenario answers four questions: *Why does it happen? What must the engine decide? What does the trusted person see? When (if ever) are they notified?*

---

## F1. Class, College, School & Office Schedule [P0]
**Why:** Parents/friends don't know class timings, break lengths, or when calling is safe.
**Situations:** class, lab, break, lunch, free period, college finished, office hours, meetings, holiday, weekend.
**Conditions the engine must handle:**
- Weekly timetable with **alternating weeks (A/B)** NEW, different timetable per weekday, semester start/end.
- Exceptions per date: class cancelled, extended, ends early, moved, substitute, whole day off, half day.
- **Break-length threshold** NEW: only call it "free now" if the free window >= viewer's min call window (default 10 min). A 5-minute change-over is not a call opportunity.
- **Walking/canteen buffer** NEW: effective free time = break minus buffer (default 5 min). Show "free ~25 min".
- Unexpectedly free (cancelled class) becomes a free window immediately, with a "free now" notification if opted in.
- Busy longer than expected: class extended pushes the free window and cancels a pending "free now" notification.
**Viewer sees:** "In class until 11:00", "Break 11:00-11:30 (free ~25 min)", "College finished".
**Notify:** FREE_NOW (opt-in per viewer), CLASS_CANCELLED, SCHEDULE_CHANGED, COLLEGE_FINISHED. Never for "class continues".

## F2. Exams [P0]
**Why:** "Is there one exam or two today? When is the break? Can I call?"
**Situations:** one/two exams a day, break between exams, practical/viva, study leave, exam extended (extra time), finished early.
**Conditions:**
- Exam set per date: ordered exams + breaks; breaks marked **calls OK / revision (prefer no calls)** NEW.
- **Pre-exam buffer** (default 30 min, phone submitted/off) and **post-exam buffer** (15 min, walking out) NEW.
- Exam day **overrides** that day's schedule unless owner opts to keep it.
- **Exam-season overview** NEW: "Exams Oct 12-20: 7 exams; two-exam days: Oct 14, 18." Directly answers the parent's confusion.
**Viewer sees:** "Math exam in progress until 11:00", "Between exams (revision) 11:00-12:00", "Exam finished".
**Notify:** EXAM_STARTED, EXAM_BREAK (if calls OK), EXAM_FINISHED ("Exam finished. May be free now. Call?").

## F3. Live Activity / Focus / Availability Reasons [P0]
**Why:** The friend who is asleep, studying, or busy with guests and keeps the phone silent.
**Activities:** studying, working, sleeping/nap, eating, in meeting, gym, with friends, with family, **busy with people/guests** , watching, gaming, prayer/function, chores, personal time, custom (guitar practice).
**Conditions:**
- Every activity has expected end (auto-default by type; sleep defaults to routine wake time).
- **Stale-state protection** NEW: past end with no extension means status EXPIRED; resolver falls back to schedule/routine; owner is prompted "Still studying? +15 / +30 / done". Never keep showing a false state.
- Quick extend / end now / change; each is a lifecycle event, not a new feature.
- Availability is separate from activity: calls ok / prefer not / no; messages ok / later.
- **Personal time** reassurance chip NEW: "Wants uninterrupted time (nothing is wrong)" to avoid worry.
**Notify:** ACTIVITY_STARTED only to viewers with opt-in or "important"; ACTIVITY_EXTENDED if it blocks a pending expected-free time; never every change.

## F4. Phone & Reachability [P0]
**Why:** "Why isn't he picking up?"
**States:** available, busy, silent, DND, calls unavailable/messages ok, low battery (20/10/5%), charging, phone may go offline, declared offline, no network/in flight (expected stretch) NEW, phone lost NEW, phone with someone else NEW.
**Conditions:**
- **Last intentionally shared context** (frozen snapshot, labelled with time) shown when phone offline or state is stale. Never fake real-time.
- **Staleness decay** NEW: after N hours the snapshot is badged "may be outdated".
- **Reach-through consent** NEW: "Call my companion Rahul" shows Rahul's number ONLY if Rahul is a connected user who granted `reach_through` to that viewer. Free-text numbers typed by the owner are the owner's responsibility and visible only to chosen viewers.
- Battery alerts once per threshold per charge cycle.
**Notify:** BATTERY_LOW/CRITICAL, PHONE_MAY_GO_OFFLINE (with companion + ETA if known).

## F5. Travel, Commute & Vehicles [P0]
**Why:** "Where is he? Which cab? When will he reach?"
**Modes:** walk, bike, auto, cab, bus, train, flight, own vehicle, carpool.
**Fields:** destination (+kind: home/college/office/other), depart, ETA, mode, companions (connected users or free text), vehicle/cab number, driver name/phone (details level only), route/bus number.
**Lifecycle:** Planned -> Travelling -> Delayed -> Arrived -> (Returning as a NEW trip) -> Completed. Also Plan Changed (destination/ETA/companion edits) and Cancelled.
**Conditions:**
- ETA overdue is derived by the resolver ("running late") without mutating the trip; the workflow handles notification.
- Delay notification only when ETA shifts >= 10 min (configurable).
- **Night-travel suggestion** NEW: after 9 PM, prompt "Turn on Arrival Watch?"
- **Expected offline stretch** NEW: overnight train / flight: "No signal until 06:30"; suppresses missing-arrival escalation inside that window.
- Arrival by one-tap "Arrived safely". Location auto-detect is NOT built; optional geofence is Future with explicit consent.
- Return trip: "Heading home" is just a new trip prefilled with home.
**Notify:** TRAVEL_STARTED, TRAVEL_DELAYED, PLAN_CHANGED, TRAVEL_ARRIVED.

## F6. Arrival Watch / Check-on-Me / Safety Context [P0 watch, P1 packet]
**Why:** Worry when someone is late and unreachable.
**Flow:** owner sets expected arrival + grace -> Temporal waits -> if no arrival: first nudge **to the owner** ("Did you arrive?") -> if still silent after escalate window: notify permitted viewers with **neutral wording**: "Arrival confirmation is missing" (never "in danger").
**Conditions:** battery-critical shortcut, delay by owner pauses watch, offline-stretch exemption, quiet-hours bypass only for this kind, false-alarm cancel sends "All good" to everyone previously alerted.
**Context packet [P1]:** one-tap share of current activity, destination, companion, vehicle, battery, last update to chosen viewers, auto-expiring (default 6h).
**Disclaimer:** not an emergency service; show emergency-number button (India: 112).

## F7. Message Drop [P0]
**Why:** Faster and lighter than chat; carries context.
**Quick chips:** Can't talk right now, Running late, Call you at ..., Class got cancelled, Someone came over, Dinner at ..., Phone might die.
**Conditions:** standalone or attached to an activity; expires (default 12h); reactions are quick replies only ("OK", "Call me later"); no threads.
**Promise/callback commitment** NEW [P1]: "I'll call at 10" creates a promise. If not marked called by 10:05, the owner is reminded and the receiver sees "Call pending". Temporal PromiseWorkflow.

## F8. Connection Reminders [P0 basic, P1 smart]
**Why:** People mean to call and forget.
**Types:** manual, recurring (call Dad every Sunday evening), routine-based, important person, planned call, missed connection, availability-aware ("You're free now. You haven't connected with Mom today. Call?").
**Conditions / anti-nag:** max 2 nudges/day/plan, cooldown doubles after dismissal, quiet hours, snooze, skip today.
**Honesty:** the app cannot see call logs. "Connected" = owner taps Called/Mark connected (or confirms after tapping Call). Never infer relationship behavior beyond configured rules.
**Long-distance** NEW: show overlap windows across time zones and respect the other person's visible sleep window.
**Smart [P1 TabPFN]:** rank free windows by predicted pick-up probability for that exact pair.

## F9. Custom Scenarios [P0 time-based, P1 event-based]
**Why:** Users teach the app their own life.
**Triggers:** time/recurrence (P0), activity state change e.g. "studying > 2 h" (P1), battery threshold (P1), leaving college (event, P1), manual.
**Effects:** set activity, set availability, suppress notifications (to audience), notify audience, create reminder.
**Examples:** "Every Wednesday 6-8 library, studying, no calls." / "Fridays 7-8 PM gaming, don't notify parents unless they call." / "When studying > 2 h, tell Mom I'm busy."
**Rules:** audience can never exceed grants (engine drops and warns, never auto-grants); conflicts resolved by priority, then specificity, then **most restrictive wins**; scenarios are pausable; every fire is logged.
**"Unless they call"** becomes the **Urgent override** NEW [P1]: viewer opens state, sees "Gaming until 8, asked not to be called", can tap "Urgent" to send a high-priority alert; rate-limited and owner-disableable per viewer.

## F10. Social Coordination: Meet-ups, Roommates, Families [P1]
- Meet-up: several users share ETA/status for one event via a temporary share link; auto-expires.
- Roommate: cooking, shopping, "need anything from outside?", **guests coming heads-up** NEW, quiet hours.
- Family routines: recurring school pickup/office/gym shared between members.
- **Companion proxy-post** NEW [P2]: Rahul posts "Arjun is with me, his phone died" only if Arjun pre-granted `can_post_for_me` to Rahul.

## F11. Partner & Emotional Nuance [P1]
Sleep/time-zone sync, "reached office", lunch-break call, "Personal time (not about you)". Wording choices are part of the feature.

## F12. Elder / Low-friction Mode [P2]
Big-button UI, one-tap "I'm fine" **daily check-in** NEW (missed check-in notifies chosen family, neutral wording), "Medicine taken", "Resting, call after 4", voice-first updates. Architecture already supports it (activities + reminders + templates).

## F13. Sensitive & Special Situations [P0 privacy primitive]
Hospital visit, family function, funeral, prayer: owner may not want the label shared.
**Private-label mode** NEW [P0 simple, P1 per-viewer]: activity displays as generic "Busy" (or "Personal") to selected viewers while the real label stays private.
**Sharing Pause** NEW [P0]: instantly pause all sharing (optionally with expiry) with a neutral viewer-side message "Sharing paused", never an alarming one.

## F14. AI-assisted Layer (cross-cutting) [P0 parse, P1 rest]
- Natural-language activity creation (multi-item: "class till 4, then home with Rahul, reach by 5").
- Natural-language scenario creation; exception creation ("physics lab cancelled today").
- Context extraction: activity, times, duration, destination, companion, ETA, availability, battery, notification preference, message.
- Missing-info prompt: "Phone is dying, going home" asks for companion + ETA.
- Smart notification judge: for free-text/custom events only; deterministic rules set the floor.
- Daily summary [P1]: "College -> Exam -> Travelling -> Arrived home", private to owner unless shared.
- Languages: English, **Hinglish** and Tamil-English code-mix are first-class test cases (your real users).
- Ambiguity handling: AM/PM, duplicate names, contradictory times -> ask, never guess silently.
- Safety: output validated against JSON schema; user confirms draft; user text shown to others is sanitized.

## F15. Platform edge cases (must not be forgotten)
Timezones and travel across zones; device clock skew; offline create-then-sync (show created vs sent time); duplicate/conflicting updates (last-write-wins with version check); block/mute user; account deletion + data export; revoke while notification pending (drop it); abuse and coercive-control mitigation (mutual connection, visible "who can see me" page, instant pause, no covert viewing, no default location, user told when access is granted); minors (parents of minors: the minor can see exactly what is shared).

---

## Crosswalk: your 40 scenarios -> families
| # | Scenario | Family | | # | Scenario | Family |
|---|---|---|---|---|---|---|
| 1 | Class Schedule | F1 | | 21 | Missed Arrival | F6 |
| 2 | Break Reminder | F1 | | 22 | Emergency Context | F6 (packet P1) |
| 3 | Exam Mode | F2 | | 23 | Temporary Sharing | F10 / share links P1 |
| 4 | Studying | F3 | | 24 | Family Routine | F10 |
| 5 | Sleeping | F3 | | 25 | Unexpectedly Free | F1 |
| 6 | Busy With People | F3 | | 26 | Busy Longer Than Expected | F1/F3 |
| 7 | Phone on Silent | F4 | | 27 | Personal Time | F3/F11 |
| 8 | Do Not Disturb | F4 | | 28 | Meet-up | F10 |
| 9 | Available Now | F3 | | 29 | Roommate | F10 |
| 10 | Calls No, Messages Ok | F4 | | 30 | Long-Distance | F8/F11 |
| 11 | Low Battery | F4 | | 31 | Loved-One Call Reminder | F8 |
| 12 | Phone Offline | F4 | | 32 | Missed Connection | F8 |
| 13 | Travelling | F5 | | 33 | Important Person | F8 |
| 14 | Cab/Vehicle | F5 | | 34 | Routine Reminder | F8 |
| 15 | Arrived Safely | F5 | | 35 | NL Activity Creation | F14 |
| 16 | Heading Home | F5 | | 36 | AI Context Extraction | F14 |
| 17 | Trip Delayed | F5 | | 37 | AI Smart Notification | F14 |
| 18 | Plan Changed | F5 | | 38 | AI Daily Summary | F14 (P1) |
| 19 | Going Somewhere | F5 | | 39 | AI Missing-Info Prompt | F14 |
| 20 | Check on Me | F6 | | 40 | Custom User Scenario | F9 |

## Decisions I made for you (change any, then tell the agent via MEMORY.md)
1. Defaults: min call window 10 min, buffer 5 min, delay-notify threshold 10 min, check-on-me grace 15 min + 15 min escalate, message expiry 12 h, context packet 6 h.
2. No location tracking in MVP. Arrival is a manual tap.
3. "Connected" is manual-confirm (no call-log access).
4. Notification channels: in-app live (SSE) in P0, web push in P1. No SMS/WhatsApp.
5. Voice, Tinker, proxy-post, elder mode are P2 and may be dropped without harming the story.
