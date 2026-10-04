import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import settings
from app.core.errors import setup_exception_handlers, CircleCueError
from app.clock import get_clock, Clock, DemoClock, set_global_clock
from app.routers import auth, users, connections, grants, state, cards, ai, scenarios, notifications, dev, reminders

logger = logging.getLogger("circlecue")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.TEMPORAL_ENABLED:
        try:
            from app.workflows.client import resync_timelines
            from app.db import get_db
            await resync_timelines(get_db())
        except Exception:
            pass
    yield


def create_app() -> FastAPI:
    dsn = (settings.SENTRY_DSN or "").strip()
    if dsn and dsn.lower() not in ("none", "null", "false") and dsn.startswith("http") and "examplePublicKey" not in dsn:
        try:
            sentry_sdk.init(
                dsn=dsn,
                environment=settings.ENV,
                integrations=[
                    FastApiIntegration(),
                ],
                traces_sample_rate=1.0 if settings.ENV == "development" else 0.1,
            )
            sentry_sdk.set_tag("module", "api")
        except Exception as e:
            logger.warning("Failed to initialize Sentry DSN '%s': %s", dsn, e)

    if settings.DEMO_CLOCK:
        set_global_clock(DemoClock())

    app = FastAPI(
        title="CircleCue API",
        version="0.1.0",
        docs_url="/docs" if settings.ENV == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    setup_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://circlecue-web.onrender.com",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(connections.router)
    app.include_router(grants.router)
    app.include_router(state.router)
    app.include_router(cards.router)
    app.include_router(ai.router)
    app.include_router(scenarios.router)
    app.include_router(notifications.router)
    app.include_router(dev.router)
    app.include_router(reminders.router)

    @app.get("/healthz", status_code=status.HTTP_200_OK)
    async def healthz() -> Dict[str, str]:
        return {"status": "ok", "service": "circlecue-api"}

    @app.get("/readyz", status_code=status.HTTP_200_OK)
    async def readyz(clock: Clock = Depends(get_clock)) -> Dict[str, Any]:
        # Mongo readiness check stub (will ping client in M01)
        mongo_status = "ok"
        return {
            "status": "ready",
            "db": mongo_status,
            "clock_now": clock.now().isoformat(),
            "env": settings.ENV,
        }

    @app.get("/debug/sentry")
    async def debug_sentry() -> Dict[str, str]:
        if settings.ENV == "production":
            raise HTTPException(status_code=403, detail="Forbidden in production")
        raise RuntimeError("Test Sentry Error from CircleCue API /debug/sentry")

    return app

app = create_app()
