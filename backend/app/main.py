"""FastAPI application entry point.

Typed request/response models mean the OpenAPI schema and the interactive
docs at /docs are generated from the same definitions the code enforces.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, analytics, auth, executions, training, workflows
from app.core.config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("eail")

DESCRIPTION = """
Reference implementation of an enterprise AI enablement platform.

**What it does**

* Role-based library of approved, versioned AI workflows
* Governance pre-flight: sensitive-data detection, policy checks, moderation
* Three-layer evaluation: deterministic checks, LLM-as-judge, human review
* Adoption, quality and cost analytics, including cost per approved output

Authenticate via `POST /auth/login` and send the returned bearer token.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting Enterprise AI Enablement Lab (env=%s, provider=%s)",
        settings.app_env,
        settings.ai_provider,
    )
    if settings.ai_provider == "stub":
        logger.info(
            "AI_PROVIDER=stub: responses are deterministic fixtures, not model output."
        )
    yield


app = FastAPI(
    title="Enterprise AI Enablement Lab",
    version="0.1.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)

# Outside production any localhost port is accepted, because the frontend is
# routinely started on whatever port happens to be free. In production only the
# explicitly configured origins are allowed.
cors_kwargs: dict = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.app_env != "production":
    cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(auth.router)
app.include_router(workflows.router)
app.include_router(executions.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(training.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "ai_provider": settings.ai_provider,
        "provider_configured": settings.provider_configured,
    }
