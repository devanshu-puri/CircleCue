# AGENTS.md: Rules for the coding agent (read at the start of EVERY session)

## 0. Session protocol
1. Read `/docs/MEMORY.md` fully. It is the source of truth. If this prompt or a module conflicts with MEMORY.md, MEMORY.md wins; log the conflict in `/docs/PROPOSALS.md` and continue.
2. State which module you are on and its Definition of Done.
3. When finished: run tests, update MEMORY.md (Build Status + Decision Log), commit with `feat(Mxx): ...`.

## 1. Product identity (never drift)
Private, permission-based activity and context network for trusted people. Every person is a normal user; there is NO "parent mode" or "friend mode". Relationship changes permissions and presets only. Not a public feed, no likes, no followers, no chatbot, no continuous location tracking, no hidden monitoring.

## 2. Non-negotiable architecture rules
1. **One visibility choke point.** All reads of another user's data (REST, SSE, notification rendering, AI context) go through `domain/visibility.py`. No router may query another user's data directly.
2. **Cards are configuration over one engine.** Never create per-scenario endpoints, collections, or tables. New situation = new template/type/config, not new architecture.
3. **State is resolved, not stored.** `domain/resolver.py` is a pure function `(user data, now) -> ResolvedState`. The UI must be correct even if Temporal is down.
4. **Temporal only triggers.** Workflows decide WHEN something happens; the resolver decides WHAT is true; the notification pipeline decides WHO is told.
5. **AI is behind an adapter.** App code calls `ai.service`, never a vendor SDK. Model is swappable by env var.
6. **AI never authorizes, never does date math, never writes to DB directly.** It returns schema-validated drafts. The user confirms. Deterministic code resolves times, matches people, and checks permissions.
7. **Provenance on every shared fact:** `user_shared | ai_parsed_user_confirmed | system_inferred | system_collected`. Show provenance in UI where it matters ("Last shared 6:42 PM").
8. **Time:** store UTC, resolve in the owner's timezone, use the injected `Clock` (supports demo clock). Never call `datetime.now()` in domain code or inside Temporal workflows (use `workflow.now()`).
9. **Defaults are private.** New connection = zero access until the owner grants. Scenarios and AI can never widen visibility beyond existing grants.
10. **Revocation is immediate:** re-check grants at read time AND just before notification delivery AND on SSE streams.
11. **Additive changes only** to schemas and file layout after M01. Renaming collections/fields, moving top-level folders, or swapping frameworks requires a DECISION entry and a migration note first.

## 3. Hallucination guards
- Before using any partner SDK (Temporal, Sentry, TabPFN, Tinker, vLLM/Ollama, Render/DO config) from memory, check the installed version (`pip show`, `npm ls`) and read the official docs or `--help`. If you cannot verify, write a clearly marked adapter stub + `TODO(verify)` instead of guessing the API.
- Pin dependency versions. Never invent endpoints, env vars, or model names; list them in `.env.example` only when real.
- If a requirement is ambiguous, pick the default in MEMORY.md; if none, choose the simplest option, log it in `/docs/DECISIONS.md`, and proceed. Do not stall.
- Do not add features not in MEMORY.md scope. Put ideas in `/docs/PROPOSALS.md`.

## 4. Stack (locked)
Frontend: Next.js (App Router) + TypeScript strict + Tailwind, PWA. Backend: Python 3.12, FastAPI, Pydantic v2, PyMongo async client (not Motor). DB: MongoDB Atlas. Workflows: Temporal (Python SDK). AI: open-weight Gemma via OpenAI-compatible endpoint (vLLM/Ollama). Monitoring: Sentry. Hosting: Render (app) + DigitalOcean (GPU model). Lint: ruff, eslint. Tests: pytest, vitest (light).

## 5. Code standards
- Typed everywhere; Pydantic models are the API contracts; generate TS types from OpenAPI.
- Small modules, no god files. Domain logic has zero framework imports.
- Every public function in `domain/` has a unit test. Resolver, visibility, lifecycle, time parsing need table-driven tests.
- Errors: typed exceptions, never swallow. AI/notification/workflow failures go to Sentry with context tags (no personal text).
- Logging: no raw user free-text, no tokens, no share codes in logs.
- Secrets only via env. `.env.example` maintained. No secrets in repo.

## 6. Security and privacy rules
Argon2 password hashing; JWT in httpOnly+Secure cookie; same-origin API via Next.js rewrites; rate limit auth, code lookup, AI parse, urgent override; audit-log grant changes, revocations, share-code use, safety events; sanitize and length-limit any free text shown to others; user can pause all sharing instantly; user can see exactly who can see what. Not an emergency service: safety UI must say so and offer a plain emergency-number button.

## 7. Definition of Done (every module)
Code + tests pass; no TODO without an owner entry in MEMORY.md; endpoints documented in OpenAPI; MEMORY.md updated; a manual smoke step written in `/docs/SMOKE.md`; Sentry capturing at least one forced test error for backend modules.

## 8. Do NOT
Add a generic chatbot; add vector DB or web search; add microservices; track location by default; send data about user A to the model when processing user B; store raw AI inputs unless the user opted in; build for partners we do not use; rewrite existing modules to "improve style".

## 9. Design rules (locked; supplied by user)
Source of truth: `design/DESIGN.md`, translated by `design/APP_DESIGN_MAPPING.md`, tokens in `design/tokens.css`.
- One accent (Action Blue). No other brand/state colors. Only extension: `--danger` for destructive/error text+icon (D9).
- Surface change (light vs dark tile) is the emphasis and divider tool; availability is mapped to tile surface AND text AND icon.
- No shadows except `.product-shadow` on photos; no gradients; no weight 500; pills for actions; press = scale(0.95); 44px targets; body 17px.
- Never hard-code hex, radii or fonts outside tokens. CI lint enforces this (M10).
- If a needed UI element is missing from DESIGN.md, compose it from existing tokens and log it in `docs/DECISIONS.md`; do not invent new visual language.
