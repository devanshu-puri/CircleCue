# DEVLOG: Real decisions, failures, and fixes

## Module M00: Scaffold, config, local compose, Sentry stub
- **Date**: 2026-10-03
- **Actions**:
  - Scaffolded monorepo structure according to MEMORY.md section 4 (`apps/api`, `apps/web`, `infra`, `docs`, `design`, `scripts`).
  - Created `apps/api/app/config.py` with typed Pydantic `Settings`.
  - Created `apps/api/app/clock.py` implementing `Clock` protocol with `SystemClock` and injectable `DemoClock`.
  - Configured typed domain error hierarchy in `apps/api/app/core/errors.py`.
  - Created `apps/api/app/main.py` with `/healthz`, `/readyz`, and `/debug/sentry` endpoints + Sentry initialization.
  - Set up Next.js `apps/web` with TypeScript strict, Tailwind, design tokens, and API rewrites in `next.config.mjs`.
  - Authored `infra/docker-compose.local.yml` booting Mongo, Temporal dev server, Ollama, API, and Web containers.
  - Created `.env.example` and `Makefile`.
