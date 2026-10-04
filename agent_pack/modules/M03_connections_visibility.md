# M03: Connections, grants, visibility engine (privacy core)
**Depends on:** M02. Most security-critical module. Write tests first.

## Build
1. Connection flow: `POST /connections/request {code}` -> pending; `POST /connections/{id}/accept|decline|block`; `DELETE` removes. Mutual and permission-based; accepting grants NOTHING.
2. Grants (owner -> viewer): `PUT /grants/{viewer_id}` with per-card AccessLevel (schedule, exam, live, travel, phone, safety, message), notify flags, important, reach_through, expires_at. `DELETE` / revoke is immediate. Presets (parent, friend, sibling, partner, roommate, grandparent) only prefill the UI; owner confirms.
3. `GET /grants/outgoing` ("who can see me, and what") and `GET /grants/incoming` ("who shares with me").
4. **`domain/visibility.py`** (pure + repo-backed):
   - `can_view(viewer, owner, card, level) -> bool`
   - `project(resolved: ResolvedState, grant, now, viewer_id) -> ViewerState` (redaction by level: status = what/until/availability; details = + companions, vehicle, message text, subject; none = null)
   - applies `sharing_paused` (viewer sees neutral "Sharing paused"), `private_label` (shows "Busy"/"Personal"), grant expiry/revocation, activity-level `visibility.mode`.
   - `viewers_for(owner, card, kind)` returns notification candidates.
5. Temporary access: grants with `expires_at`; expired == none. Share links (card/activity codes like TRV-92KD) are P1: table + stub endpoints, expiring, revocable, max_uses.
6. Audit every grant change/revoke/share-code use. Notify owner when a new viewer is granted? (No: owner is the one granting.) Notify viewer when access is revoked: NO (avoid conflict); silently becomes unavailable.

## Edge cases
Block removes connection and grants both ways. Duplicate requests idempotent. Self-connect rejected. Grant to non-connected user rejected. Grant change while notification pending: pipeline re-checks (M08).
## Tests (table-driven, exhaustive): every card x every level x paused/expired/revoked/private-label; no leakage of any field above granted level; viewer cannot read non-granted card via any endpoint.
## DoD: 100% branch coverage on visibility.py. Update MEMORY.md.
