# M02: Auth, profile, routine, universal code
**Depends on:** M01.

## Build
1. `POST /auth/register|login|logout`, `GET /me`, `PATCH /me`. Argon2 hash; JWT in httpOnly Secure SameSite=Lax cookie; short expiry + refresh via re-login (keep simple).
2. Profile: name, avatar (URL upload to simple storage or data-URI limited size; Render disk not assumed; use small base64 or external URL), tz, routine_prefs (wake, sleep, min_call_window_min, buffer_min), quiet hours.
3. **Universal code:** `NAME-XXXX` (first name uppercased, up to 6 chars, + 4 chars from alphabet `23456789ABCDEFGHJKMNPQRSTUVWXYZ`). Unique index, retry on collision, `POST /me/code/rotate`. Lookup endpoint returns only first name + avatar, rate-limited (10/min/user), constant-ish timing, same response shape for not-found.
4. Routine wizard backend: `PUT /me/routine` writes ROUTINE templates (wake/sleep/college/lunch/study blocks) via M05 template service interface (stub if M05 not ready; add TODO).
5. Sharing pause: `POST /me/pause {until?}` and `DELETE /me/pause`.
6. Block/mute and account delete + data export (`GET /me/export` JSON) stubs with real data export of owned documents.
7. Audit log on login failures, code rotation, pause toggles.

## Edge cases
Password reset out of scope (document). Email uniqueness case-insensitive. Rotating code does not break existing connections.
## Tests: auth flow, cookie flags, code format/uniqueness/rotation, rate limit, export contains only own data.
## DoD: register -> login -> /me -> code visible. Update MEMORY.md.
