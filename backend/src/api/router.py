"""Top-level API routes grouped by health and bounded context."""

from fastapi import APIRouter

from api.health.metrics import router as metrics_router
from api.health.routes import router as health_router
from api.identity.router import router as identity_router
from api.platform.router import router as platform_router

router = APIRouter()
router.include_router(health_router)
router.include_router(metrics_router)
router.include_router(identity_router)
router.include_router(platform_router)
