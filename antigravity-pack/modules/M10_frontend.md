# M10: Frontend (Next.js PWA), Apple-style design system
**Depends on:** M02-M09 APIs. **Design law:** `design/DESIGN.md` + `design/APP_DESIGN_MAPPING.md` + `design/tokens.css`. Read all three BEFORE writing any UI. Do not invent a brand; do not add colors, shadows, gradients or font weights.

## Step 0: design foundation (do first, commit separately)
1. Import `design/tokens.css` globally. Extend Tailwind theme from the tokens (colors, radii, spacing, font families) so utilities resolve to CSS variables; disable default palette. Load Inter via `next/font` as fallback behind the system stack.
2. Build primitives only from DESIGN.md component names: `GlobalNav`, `SubNavFrosted`, `BottomTabBar` (floating-sticky-bar look), `Tile` (variants: light, parchment, dark, dark2, dark3), `PillButton` (primary, ghost), `UtilityButton`, `Chip` (option, selected), `UtilityCard`, `SearchInput`, `Switch` (ext D8), `ProvenanceCapsule`, `Footer`, `Sheet` (frosted).
3. Add lint/CI rules from APP_DESIGN_MAPPING section 7. Add a `/design-check` dev page rendering every primitive for visual QA on phone width.

## Principles
Understandable in seconds, mobile-first (PWA on phone), people-first and state-first. Surface encodes availability (light = reachable, dark = busy) always with text + icon. One hero input. Cards are one reusable `UtilityCard`/`CardShell`.

## Screens (rhythm and component mapping in APP_DESIGN_MAPPING sections 3-4)
1. **Onboarding:** one tile per step (register, profile, routine wizard, optional "describe your day" via AI, show universal code + share), alternating light/dark.
2. **Home (me):** `GlobalNav` -> `SubNavFrosted` ("Today" + Update pill) -> **state hero tile** (display-lg state, lead detail, pills Extend / Done) -> composer tile (`SearchInput` NLComposer + quick chips Studying, Free now, Going home, Phone low, Can't talk) -> cards grid tile -> timeline tile.
3. **ConfirmSheet:** after AI parse show editable draft cards with resolved times, `ProvenanceCapsule` "AI-parsed. Confirm.", warnings, and `missing` questions as inline chip choices ("Who are you with?" companion disambiguation with selected-chip state, ETA field). Actions: Confirm (primary), Edit (ghost), Discard (text-link).
4. **People:** connection cards with status line (only what they chose to share); add by code; requests. **Person page:** hero tile of their ViewerState; pills Call / Message; text-link Remind me; best-time-to-call (P1, labelled system-inferred); Urgent (P1) when "no calls" with a confirm step; timeline; granted detail cards only.
5. **Permissions:** per-person utility card, card x level chip pickers, notify `Switch`es, preset picker (prefills only), expiry, Revoke (danger text). "Who can see me" summary line. Pause-sharing `UtilityButton` at top.
6. **Notifications center:** live via SSE with reconnect/backoff, action pills, read state, mute. High-urgency kinds pin as a dark tile at top.
7. **Scenarios:** list, NL create with plain-English preview, enable/pause `Switch`.
8. **Exam season view:** date list, break flags, two-exam-day callouts.
9. **Settings + privacy:** routine prefs, quiet hours, note "running on an open model, self-hosted", export/delete, `Footer` with privacy statement.

## Engineering
- API client from generated OpenAPI types; SWR/React Query; SSE hook.
- Staleness UI everywhere: "Last shared 6:42 PM", muted, never styled as live.
- PWA manifest, installable, offline shell; web push hook (P1).
- Accessibility: 44px targets, labels, focus ring, reduced motion, state never by color alone, large-text flag for elder mode (P2).
- Demo clock banner (dev/demo only) using a parchment frosted strip.
- Sentry browser init; error boundary around each card; loading/empty states per D12.

## Edge cases
Long names/labels truncate with accessible full text; viewers with all cards "none" see a neutral "Nothing shared yet" tile; paused sharing shows neutral parchment tile; offline shows last cached state labelled "Offline. Showing last update."

## DoD: all 5 demo workflows run through the UI at 390px width; lint rules pass; `/design-check` page matches DESIGN.md; no hex/shadow/weight-500 violations. Update MEMORY.md (D8-D12).
