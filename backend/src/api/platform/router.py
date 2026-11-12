"""Developer Platform HTTP router assembled by feature."""

from fastapi import APIRouter

from api.platform.application_delivery.routes import router as application_delivery_router
from api.platform.catalog.routes import router as catalog_router
from api.platform.operations.routes import router as operations_router
from api.platform.projects.routes import router as projects_router
from api.platform.resources.routes import router as resources_router

router = APIRouter(prefix="/api/v1")
for feature_router in (
    catalog_router,
    projects_router,
    resources_router,
    operations_router,
    application_delivery_router,
):
    router.include_router(feature_router)
