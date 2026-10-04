# SMOKE Test Procedures
Manual smoke steps for verification.

## M03: Connections and grants
1. Register two users, A and B, and copy B's user code.
2. As A, call `POST /connections/request` with B's code. Confirm the connection is pending.
3. As B, accept the connection. Confirm no grant was created automatically.
4. As B, request `GET /state/{A}`. Confirm state fields are null while no directional grant exists.
5. As A, call `PUT /grants/{B}` with `{"cards":{"travel":"status"}}`. Confirm outgoing grants show the travel status permission and incoming grants for B show the same permission.
6. As B, request `GET /state/{A}`. Confirm travel status is visible but destination, companion, and vehicle details are absent.
7. As A, call `DELETE /grants/{B}`. Repeat the state request as B and confirm all projected context is unavailable immediately.
8. Grant access again, then block or remove the connection. Confirm all grants are revoked and B cannot read A's state.
9. In `/permissions`, verify a connection with no grant opens with all card levels at Details and all alert switches on. Turn off one card and one alert, save, reload the page, and verify the selections persist. Before saving, verify B still cannot read A's state; connection acceptance alone must not create access.
10. With an active grant, open B's People detail for A. Update A's live activity and confirm B's detail refreshes within 10 seconds and remains limited to the saved card grants. Revoke or pause A's sharing and confirm the next refresh removes the shared state.

## M04: Resolver and timelines
1. Seed an owner routine and a Saturday `CLASS` template from 09:00 to 10:00 in `Asia/Kolkata`; set calls to `no` and visibility to `private_label` with label `Personal`.
2. Call `GET /state/me` at a time inside the slot. Confirm the resolved activity is the class and calls are unavailable.
3. Call `GET /timeline?date=2026-10-03` as the owner. Confirm the real title and UTC-converted boundaries are returned.
4. Grant a connected viewer schedule `status` access. Call `GET /timeline/{owner_id}?date=2026-10-03` as that viewer; confirm the label is `Personal`, timing and call status remain visible, and detail fields are absent.
5. Change the slot with a date exception and repeat the timeline request. Confirm the exception is reflected without storing a separate resolved-state record.
6. Set an activity expected end in the past and resolve again. Confirm it is ignored and the schedule/routine layer becomes current.
7. Set a sharing pause with an expiry. Confirm it is active before `until` and ignored after `until` using the injected/demo clock.

## M05: Cards
1. Register an owner and create a schedule slot with `POST /cards/schedule`; confirm the server sets the owner and `SCHEDULE_SLOT` kind.
2. Read `GET /cards/schedule`, then resolve `GET /timeline?date=2026-10-03`; confirm the created slot appears.
3. Update the slot with its current `version`, then retry with the stale version and confirm a 409 response. Delete using the latest version.
4. Bulk-save the timetable at `PUT /cards/schedule/bulk`, including current versions for existing slots. Confirm omitted owner slots are removed and stale versions return 409.
5. Create a date exception at `POST /cards/schedule/exceptions`; confirm it appears in `GET /cards/schedule/exceptions` and changes the expanded timeline.
6. Create an exam set with two exams; call `GET /cards/exam/season` and confirm the date is marked as a two-exam day.
7. Create a live activity, update it with its current version, and confirm it transitions to `CHANGED`; retry the previous version and confirm 409.
8. Create a planned travel card, change it to `ACTIVE`/`travelling`, then update its ETA. Confirm it moves to `CHANGED`/`delayed` without creating a second trip.
9. Set the phone battery to 5% or `may_go_offline=true`; confirm the stored bucket and timestamped frozen context are present.
10. Create a message from a quick template, grant message-details access, and react as an audience member. Confirm unconnected/ungranted audiences and stale reaction versions are rejected.
11. Call `POST /cards/safety/context`; confirm it returns 501 until the expiring P1 packet flow is implemented by M08.

### Web card editor regression smoke
1. Sign in and open `/me/schedule`; confirm existing schedule slots load. Add one slot and confirm it appears after save; edit/remove through the schedule controls and confirm changes remain after reload.
2. Open `/me/exam`; confirm existing exam sets load. Add an exam, edit its subject/time/buffers, save, and confirm the same date's set updates after reload.
3. Open Quick Update, parse text with a missing field (for example a travel destination), answer every missing question, choose **Update Draft & Review**, then confirm the refreshed draft. Confirm incomplete drafts cannot be applied and API errors are visible in the form.
4. From an account that received a pending connection, open `/people`; confirm the requester's name is shown, accept the request, and verify both accounts show the active connection.
5. Open Quick Update and parse `I will be studying by 6 pm`; confirm the API accepts the request, shows a study draft, and confirmation returns a saved record.
6. Open `/me/travel`; start a journey with destination, expected arrival, companion name, optional companion phone, optional return time, and Arrival Watch. Confirm it appears after save and reload. Edit its destination/times/phone and confirm the same journey updates without changing its lifecycle phase. Confirm status-only viewers do not receive the companion phone or return time, while details viewers do.
7. Open Quick Update and parse an unrelated string such as `yzdf`; confirm it shows a clear recovery message and cannot be saved. Parse `i am going for lunch with my friend rakka`; enter `hostel mess` and `within 10 min` for the prompted destination/ETA and confirm the revised draft contains the destination and resolved arrival before saving.
8. On `/me`, set the ringer mode and battery percentage and save; reload and confirm the saved values are selected. Save again with different values and confirm they update rather than returning a duplicate-record error. From the dashboard, open Phone and confirm it scrolls to the phone controls. Open Schedule, Exams, Travel, and Messages, then use “All cards” and confirm each returns to the card hub.
9. Create two overlapping live updates with different end times. On the dashboard, finish the current live update early and confirm the next stacked update becomes current; let another update reach its expected end and confirm the resolver moves on automatically. Create/edit/delay/cancel a travel card and confirm the destination, ETA, companion phone, return time, and lifecycle remain correct after reload. Confirm titles containing quotes display as ordinary readable text.

## M06: AI drafts
1. Register an owner in `Asia/Kolkata`; connect a second account and add a schedule template.
2. Call `POST /ai/parse` with `{"text":"studying till 8, no calls","mode":"activity"}`. Confirm an editable activity draft, resolved UTC end time, `no` calls, and one `ai_invocations` record; confirm no activity was stored.
3. Parse `Going home with Rahul, reach in 40 min, battery 5%` with Rahul connected. Confirm travel and phone drafts, relative ETA resolved by code, and the companion linked by owner connection only.
4. Parse with duplicate connected first names; confirm the companion remains unresolved and a question is returned.
5. Confirm the activity draft through `POST /ai/confirm`; verify provenance is `ai_parsed_user_confirmed`. Repeat as another account and confirm it is rejected.
6. Set `ai_prefs.store_raw=true`, parse again, and confirm raw text is recorded only for that owner. Restore false and verify later invocations omit it.
7. Stop the model endpoint while `AI_PROVIDER=ollama` or `openai_compat`; confirm the rules provider still returns a draft. Review Sentry spans for provider/model/timing/schema/intent metadata and verify no text is attached.
8. Parse `I will be studying till 6:25, no call till then` as a user whose local time is before 6:25 PM. Confirm the draft says calls are unavailable, the resolved end is 6:25 PM local time, and the dashboard shows Busy until then. Parse `I will be studying till 6:30`; confirm the same no-call default.
9. Parse `phone on silent`, `phone on DND`, and `phone on ring`. Confirm drafts explicitly display Silent, Do Not Disturb, and On ring with Messages: ok.
10. On the dashboard, open the “At home” place chip and set Home, College, Library, Friend's place, and a custom value; reload and confirm each persists. Clear it and confirm the chip returns to “At home”. As a connected viewer, verify the place is hidden without Travel DETAILS and visible with Travel DETAILS. Confirm no location permission or GPS prompt appears.
11. Create two active live updates. In “Active Status Log,” remove one with the × control; confirm it disappears and the next active update becomes current. Reload to verify completion persisted, and confirm unrelated schedule/travel records remain unchanged.
12. Connect two users and grant one MESSAGE DETAILS plus the message notification toggle. Drop a note with the default “all granted connections” audience; confirm it appears in that viewer's People detail under Dropped messages and only eligible notifications are sent. Confirm an ungranted connection and a different explicit audience do not expose the text, status-only access never exposes text, expired messages disappear, and pause/revocation immediately hides it. Grant PHONE STATUS and confirm mode/battery bucket only; upgrade to DETAILS and confirm exact battery percent. Grant TRAVEL DETAILS and confirm the owner's manually shared place appears. Grant SCHEDULE and confirm only the projected timeline appears.

## M07: Time scenarios
1. Parse and confirm `Every Friday 7-10 I play cricket, don't notify people I'm available`.
2. Call `GET /scenarios`; confirm a time trigger, `set_activity` effect, and `suppress_notifications` effect were saved.
3. Call `POST /scenarios/{id}/dry-run`; confirm next window, effect summary, and only viewers with the needed card grant in its audience.
4. Add an audience member without that grant; confirm dry-run warns they are excluded and does not create a grant.
5. Disable the scenario with its current version and resolve during its former window; confirm the scenario no longer wins layer 5.

## M08: Notifications and Temporal Workflows
1. Register owner and viewer. Connect mutually and grant `cards: {exam: "status"}, notify: {exam: true}`.
2. Create an exam set with exam from 09:00 to 11:00 and break from 11:00 to 11:30.
3. Advance clock via `POST /dev/tick` to 11:00:00 (break boundary). Confirm `EXAM_BREAK` notification is delivered to the viewer with suggested action.
4. Call `GET /notifications` as the viewer to confirm receipt. Call `POST /notifications/{id}/read` to mark read, and `POST /notifications/{id}/action` to set chosen action.
5. In another session, start travelling with `check_on_me: {enabled: true, grace_min: 2, escalate_min: 2}`.
6. Skip time past grace: confirm owner receives `ARRIVAL_MISSING` nudge ("Did you arrive?").
7. Skip time past escalate: confirm safety-granted viewer receives `ARRIVAL_MISSING` notification (bypassing quiet hours and daily rate limit).
8. Send late `arrived` signal or transition activity to `arrived`: confirm `ALL_CLEAR` notification is generated and delivered to viewer ("Arrival confirmed. All good.").
9. Create a message with `promise_at`: verify `PromiseWorkflow` triggers `PROMISE_DUE` owner reminder if not marked done within 5 minutes.
10. Grant a connected viewer LIVE STATUS and enable “Live activity updates”. Create a live activity and edit its title; confirm one `ACTIVITY_STARTED` and one `ACTIVITY_EXTENDED` alert appear in the viewer's inbox/SSE stream. Disable the activity notification toggle or revoke LIVE access and confirm no further alert is delivered.
11. Enable schedule, exam, phone, and safety card access plus their matching alert toggles. Make a schedule change, update an exam set, change phone mode/battery, and start a safety watch; confirm each supported alert appears with readable, permission-filtered content. Battery threshold alerts should fire when crossing into the configured low bucket.
12. Keep `/permissions` Alerts open while another authorized session creates an activity. Confirm SSE inserts the alert once, shows the connected sender and current text, and that browser reconnect does not duplicate it. Reload and confirm the newest alert is first; mark it read and confirm the state persists after reload.
13. Verify normal alerts stop after the documented 20-per-owner/viewer rolling-day cap, duplicate same-kind updates within the 5-minute dedupe window are collapsed, and urgent safety alerts still arrive. Pause or revoke the owner's sharing and confirm inbox reads and live delivery no longer expose their data.

## M02/M10: Pause, dashboard log, and Today summary
1. Pause sharing from the profile page. Reload and confirm the paused state remains active and a connected viewer sees no private context.
2. Resume sharing from the profile page. Confirm the server response and `GET /me` both show `sharing_paused.active=false`; reload and verify it stays resumed.
3. Create a timed live activity. Confirm Active Status Log lists it, remove it early, and verify its status is `COMPLETED` after reload. Leave a second item until its expected end and confirm it no longer appears once expired.
4. Set the profile timezone to `Asia/Kolkata` while the browser uses another timezone. Confirm Today and status-log times display in the profile timezone; Today uses the active activity's own `until` time and readable label, or labels the next resolver boundary as a next change when the current activity has no end time.

## M09: Connection Reminders

1. Register an owner. Create a connection plan via `POST /reminders/plans` with `{"target": "<peer_id>", "importance": "high", "rule": "weekly"}`. Confirm `201 Created` with `plan_id`.
2. Simulate 8 days elapsed since last contact: directly set `last_connected_at` to 8 days ago in the plan (via MongoDB or seed script), or use `POST /reminders/plans/{id}/connected` then manually update the timestamp.
3. Call `POST /reminders/check` as the owner. Confirm:
   - Response has `evaluated_count: 1`
   - One `CONNECTION_REMINDER` notification exists for the owner in `GET /notifications`
   - Notification text mentions the target's name
4. Call `POST /reminders/check` again **immediately**. Confirm `evaluated_count: 0` (same-day 4-hour cooldown is enforced).
5. Call `POST /reminders/plans/{id}/snooze` with `{"days": 3}`. Call `POST /reminders/check` again. Confirm `evaluated_count: 0` (snoozed).
6. Call `POST /reminders/plans/{id}/connected`. Confirm `status: "connected"` and `last_connected_at` is updated. Verify `POST /reminders/check` returns 0 (not due yet for a weekly plan).
7. Test pickup predictor: `POST /predict/pickup` with `{"reachability_calls": "no"}` → confirm `probability <= 0.10`.
8. `POST /predict/pickup` with `{"reachability_calls": "ok", "local_hour": 14, "battery_bucket": "ok"}` → confirm `probability >= 0.70`.
