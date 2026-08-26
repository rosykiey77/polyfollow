from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.wallets import router as wallets_router
from app.api.v1.positions import router as positions_router
from app.api.v1.trades import router as trades_router
from app.api.v1.signals import router as signals_router
from app.api.v1.statistics import router as statistics_router

api_v1_router = APIRouter(prefix="/api/v1")

# Include routes
api_v1_router.include_router(health_router)
api_v1_router.include_router(wallets_router)
api_v1_router.include_router(positions_router)
api_v1_router.include_router(trades_router)
api_v1_router.include_router(signals_router)
api_v1_router.include_router(statistics_router)
