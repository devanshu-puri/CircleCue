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

## Module M01: Data model, Pydantic schemas, indexes
- **Date**: 2026-10-03
- **Actions**:
  - Authored Pydantic v2 models in `apps/api/app/domain/models.py` covering all 16 collections in MEMORY.md 5.1 with strict field validation, HTML sanitization, and max-length constraints.
  - Implemented `ActivityType`, `Status`, `TravelPhase`, `CardKey`, `AccessLevel`, `Calls`, `Messages`, `ProvenanceSource`, `NotificationKind` enums.
  - Defined `ResolvedState` and `ViewerState` contracts (MEMORY.md 5.3).
  - Configured `apps/api/app/db.py` with PyMongo `AsyncMongoClient` and `ensure_indexes()` for collections.
  - Implemented data-driven lifecycle transition tables in `apps/api/app/domain/lifecycle.py`.
  - Created `scripts/gen_types.py` for exporting OpenAPI schema to `docs/openapi.json` and TypeScript types to `apps/web/lib/types/api.ts`.
  - Added unit tests in `test_domain_models.py` and `test_lifecycle.py` (14 passing tests).

## Module M02: Auth, profile, routine, universal code
- **Date**: 2026-10-03
- **Actions**:
  - Implemented Argon2 password hashing and JWT cookie authentication in `apps/api/app/core/security.py`.
  - Built universal code generator (`NAME-XXXX`) with unique lookup & rotation support.
  - Implemented `/auth/register`, `/auth/login`, `/auth/logout` endpoints in `apps/api/app/routers/auth.py`.
  - Built `/me`, `/me/code/rotate`, `/users/code-lookup`, `/me/routine`, `/me/pause`, `/me/export`, `/me` deletion in `apps/api/app/routers/users.py`.
  - Added audit log integration in `apps/api/app/core/audit.py` and rate limiter in `apps/api/app/core/ratelimit.py`.
  - Authored comprehensive test suite in `apps/api/tests/test_auth_and_profile.py` (17 passing tests).
