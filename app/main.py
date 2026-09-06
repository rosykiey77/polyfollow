from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import logger, setup_logging
from app.services.polymarket import polymarket_client
from app.services.webhook import webhook_service
from app.workers.poller import poller


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("Initializing %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    poller.start()
    yield
    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    await poller.stop()
    await polymarket_client.close()
    await webhook_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Headless API backend for Polymarket whale tracking and Hermes Agent intelligence streaming.",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# Enable GZip compression for payloads >= 1KB (reduces network transfer by up to 80%)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root health check endpoint (Public for Docker healthcheck)
app.include_router(health_router)

# Web Dashboard endpoint (/dashboard) - Enabled only if configured
if settings.ENABLE_DASHBOARD:
    from app.api.v1.dashboard import router as dashboard_router
    app.include_router(dashboard_router)
    logger.info("Web Dashboard UI enabled at /dashboard")
else:
    logger.info("Headless Mode: Web Dashboard UI is disabled.")

# API v1 endpoints (Protected with API Key dependency)
app.include_router(api_v1_router)


@app.get("/", tags=["Root"])
async def root():
    resp = {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mode": "headless_api" if not settings.ENABLE_DASHBOARD else "monolith_with_ui",
        "health": "/health",
        "api_v1": "/api/v1",
    }
    if settings.ENABLE_DASHBOARD:
        resp["dashboard"] = "/dashboard"
    if settings.ENABLE_DOCS:
        resp["docs"] = "/docs"
    return resp

