from fastapi import APIRouter
from .telemetry import router as telemetry_router
from .dashboard import router as dashboard_router
from .zones import router as zones_router
from .sensors import router as sensors_router
from .alerts import router as alerts_router
from .analytics import router as analytics_router
from .farmers import router as farmers_router

api_v1_router = APIRouter()

api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(zones_router)
api_v1_router.include_router(sensors_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(farmers_router)

