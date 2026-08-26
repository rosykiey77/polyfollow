from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import logger, setup_logging
from app.services.polymarket import polymarket_client
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


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated backend service for tracking Polymarket whale/bandar wallets and streaming signals to Hermes Agent.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health check endpoint
app.include_router(health_router)

# API v1 endpoints
app.include_router(api_v1_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_v1": "/api/v1",
    }
