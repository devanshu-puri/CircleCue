# M00: Scaffold, config, local compose
**Goal:** a running skeleton the rest plugs into. **Depends on:** none. **Read:** AGENTS.md, MEMORY.md.

## Build
1. Monorepo exactly as MEMORY.md section 4. Python 3.12 + uv/pip-tools; Node 20+.
2. `apps/api`: FastAPI app factory, `config.py` (pydantic-settings, all env vars typed), `clock.py` (`Clock` protocol: `SystemClock`, `DemoClock` with offset and `advance()`), `core/errors.py` (typed exceptions + handlers), `/healthz`, `/readyz` (checks Mongo, optional Temporal/AI), CORS off (same-origin).
3. `apps/web`: Next.js App Router, TS strict, Tailwind, PWA manifest, `next.config.js` rewrites `/api/:path*` -> `${API_URL}/:path*`. Empty layout with design-token CSS variables (placeholder until `design/design.md`).
4. `infra/docker-compose.local.yml`: mongo, Temporal dev server, Ollama (pull a small Gemma tag, document which), api, web. One command boots everything.
5. `.env.example` with: MONGODB_URI, JWT_SECRET, TZ_DEFAULT, AI_PROVIDER (openai_compat|ollama|rules), AI_BASE_URL, AI_MODEL, AI_API_KEY, AI_TIMEOUT_S, TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_API_KEY, SENTRY_DSN, DEMO_CLOCK, PREDICTOR_PROVIDER. Only real vars.
6. Sentry init (API + web) behind DSN presence; tags: env, module. Forced-error route `/debug/sentry` (disabled in prod unless flag).
7. CI-less: `Makefile` targets: `dev`, `test`, `lint`, `seed`.
8. Create empty `docs/` files from MEMORY.md list; copy MEMORY.md in.

## Edge cases
Missing env -> fail fast with clear message. DemoClock must be injectable via FastAPI dependency AND importable by workers.

## DoD
`make dev` boots; `/healthz` ok; web shows placeholder; test for Clock; Sentry test event received.
## Update MEMORY.md: Build Status M00.
