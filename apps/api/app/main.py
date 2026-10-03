import logging
from typing import Dict, Any
from fastapi import FastAPI, Depends, status, HTTPException
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import settings
from app.core.errors import setup_exception_handlers, CircleCueError
from app.clock import get_clock, Clock, DemoClock, set_global_clock

logger = logging.getLogger("circlecue")

def create_app() -> FastAPI:
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV,
            integrations=[
                FastApiIntegration(),
            ],
            traces_sample_rate=1.0 if settings.ENV == "development" else 0.1,
        )
        sentry_sdk.set_tag("module", "api")

    if settings.DEMO_CLOCK:
        set_global_clock(DemoClock())

    app = FastAPI(
        title="CircleCue API",
        version="0.1.0",
        docs_url="/docs" if settings.ENV == "development" else None,
        redoc_url=None,
    )

    setup_exception_handlers(app)

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
