# APP DESIGN MAPPING: how DESIGN.md (Apple-style) applies to this app
`design/DESIGN.md` is the law. This file only translates a marketing-site language into an app UI. Where DESIGN.md is silent, extensions are listed in section 6 and logged in MEMORY.md (D8-D10). Use tokens from `design/tokens.css` only.

## 1. Core idea
Photography-first becomes **people-first and state-first**. UI chrome recedes; the person's current state is the "product" on the tile. The color change between tiles is the divider and the emphasis tool. One accent (Action Blue) for every interactive element.

## 2. Surface = availability (the signature mapping)
| Resolved state | Tile | Notes |
|---|---|---|
| Available / free / break / message ok | `product-tile-light` or `-parchment` | alternate light/parchment for rhythm |
| Busy / calls: no / exam / sleeping / in class | `product-tile-dark` (`-2`, `-3` for stacked dark) | text `on-dark`, links `primary-on-dark` |
| Stale / last-shared snapshot | same tile as at share time, with caption "Last shared 6:42 PM" in `body-muted` / `ink-muted-48` | never styled as live |
| Sharing paused | `canvas-parchment` tile, neutral copy | never alarming |
**Never color alone:** every tile also carries explicit text ("Calls: No") and an icon (accessibility, color-blind safety).

## 3. Component mapping
| App element | DESIGN.md component |
|---|---|
| Top bar (logo, bell, avatar) | `global-nav` (black, 44px; collapses at 833px) |
| Page title + main action ("Update") | `sub-nav-frosted` with `button-primary` right-aligned |
| Mobile bottom tab bar (Home, People, Alerts, Me) | `floating-sticky-bar` look (frosted parchment 80%, blur) with 44px targets |
| My state / person state hero | `product-tile-*`: `display-lg` state title -> `lead` detail ("Until 8 PM, Calls: No") -> two pills |
| Primary actions (Call, Confirm, Share) | `button-primary` pill |
| Secondary (Message, Edit) | `button-secondary-pill` (ghost pill) |
| Utility (Pause sharing, Revoke) | `button-dark-utility` (8px radius) |
| Quick chips (Studying, Free now, Going home, Phone low, Can't talk) | `configurator-option-chip`; selected = 2px `primary-focus` border |
| NL composer "What's happening?" | `search-input` (pill, 44px) with leading glyph; mic reserved for P2 |
| Cards (Schedule, Exam, Travel, Phone, Message, Reminders, Scenarios) | `store-utility-card` (white, 1px hairline, 18px radius, 24px padding, **no shadow**) |
| AI confirm sheet | bottom sheet in `frosted` style; drafts as `store-utility-card`; provenance chip as `button-pearl-capsule` (non-interactive) "AI-parsed. Confirm." |
| Permission level pickers (none / status / details) | segmented `configurator-option-chip` row |
| Person row / avatar | utility card, avatar 1:1 crop at `rounded.sm`; hero avatar may use `product-shadow` (photo resting on tile) |
| Timeline | dense list on parchment tile using `dense-link` rhythm, times in `caption-strong` |
| Footer / privacy statement | `footer` |
| Onboarding steps | one full-bleed tile per step, alternating light/dark, `display-lg` + one pill CTA |

## 4. Screen rhythm (top to bottom)
- **Home:** `global-nav` -> `sub-nav-frosted` ("Today" + Update) -> **state hero tile** (light/dark by availability) -> parchment tile with composer + chips -> light tile with cards grid -> parchment timeline tile.
- **People list:** utility cards, status line per person in `caption`; unavailable people get a small dark capsule label, not a color flood.
- **Person page:** hero tile with their ViewerState; pills: **Call** (primary), **Message** (ghost); text-link "Remind me"; below: timeline tile, then exam/travel details cards (only if granted).
- **Permissions:** one utility card per person; matrix rows with chip pickers; "Who can see me" summary as `tagline`; Pause sharing as `button-dark-utility` at top.
- **Notifications:** utility cards with action pills; unread = `primary` text-link dot, not a new color.
- **Alerts of higher urgency** (ARRIVAL_MISSING, URGENT_OVERRIDE, critical battery): pinned dark tile at top of Home/People, `tagline` headline with neutral wording, primary pill "Call". Urgency comes from surface + position + copy, not a new hue.

## 5. Typography and spacing rules to enforce
- Body 17px / 400 / 1.47 (not 16). Headlines 600 with negative tracking. **No weight 500 anywhere**; 700 only for `tagline`. Weight 300 only for `lead-airy`/`button-large`.
- Fonts: system-ui stack first (real SF on Apple devices); load **Inter** (variable, via next/font) as the non-Apple fallback with `-0.01em` extra tracking on display sizes and body line-height 1.44 when Inter renders.
- 8px base spacing; tiles padded 80px desktop, 48px small phone; cards 24px; touch targets >= 44x44.
- Press state `scale(0.95)` on every button. Focus ring 2px `primary-focus`. Do not design hover states.
- Breakpoints from DESIGN.md: 1440 lock, 1068, 833, 734, 640, 480. Utility grids: 5/4/3/2/1 columns down the ladder (apply 3/2/1 realistically for our card counts).

## 6. Extensions (DESIGN.md is silent; these are the ONLY additions)
| ID | Gap in DESIGN.md | Decision |
|---|---|---|
| D8 | No toggle/switch | Pill track 51x31: on = `primary`, off = `surface-chip-translucent`, white thumb. Tokens only, no shadow. |
| D9 | No error/destructive style ("Known Gaps") | Single token `--danger` (#d70015) allowed ONLY for destructive text/icons (Revoke, Delete) and form-validation text. Never for fills, tiles, CTAs or availability states. |
| D10 | No dark-mode counterpart documented | MVP is light-dominant like DESIGN.md. No system dark-mode theme. Dark tiles are semantic (busy), not a theme. Revisit post-submission. |
| D11 | Marketing nav has no mobile app tab pattern | Bottom tab bar reuses `floating-sticky-bar` styling. |
| D12 | No empty/loading states | Loading = parchment tile skeleton with `ink-muted-48` blocks (no shimmer gradient). Empty = `lead-airy` sentence + one pill CTA. |

## 7. Hard Don'ts (lint these)
No second accent. No shadows on cards/buttons/text (only `.product-shadow` on photos). No decorative gradients (also no shimmer gradients). No `font-medium`/weight 500. No rounding on full-bleed tiles. No body line-height under 1.47 (Inter exception above). No mixing radii outside the scale. Don't use `primary-on-dark` on light surfaces.
**Add CI/lint checks:** grep fails build on hex literals outside `design/tokens.css`, on `shadow-*`/`box-shadow` outside `.product-shadow`, on `font-medium`, `bg-gradient`, `linear-gradient`.

## 8. Accessibility notes
`ink-muted-48` (#7a7a7a) on white is below 4.5:1: use only for disabled text and fine print, never for essential information (use `ink-muted-80` for readable secondary text). Dark-tile text must be `on-dark` or `body-muted` only. All state meaning has text + icon. Respect `prefers-reduced-motion` (the press scale is the only motion).
