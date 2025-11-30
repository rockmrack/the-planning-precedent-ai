"""API v1 routes"""

from fastapi import APIRouter

from .search import router as search_router
from .analysis import router as analysis_router
from .cases import router as cases_router
from .export import router as export_router
from .reference import router as reference_router
from .auth import router as auth_router
from .users import router as users_router
from .websocket import router as websocket_router
from .alerts import router as alerts_router
from .maps import router as maps_router
from .generator import router as generator_router

router = APIRouter(prefix="/api/v1")

# Core functionality
router.include_router(search_router, tags=["Search"])
router.include_router(analysis_router, tags=["Analysis"])
router.include_router(cases_router, tags=["Cases"])
router.include_router(export_router, tags=["Export"])
router.include_router(reference_router, tags=["Reference"])

# Authentication and users
router.include_router(auth_router, tags=["Authentication"])
router.include_router(users_router, tags=["Users"])

# Real-time features
router.include_router(websocket_router, tags=["WebSocket"])

# Monitoring and alerts
router.include_router(alerts_router, tags=["Alerts"])

# Maps and GIS
router.include_router(maps_router, tags=["Maps"])

# Document generator
router.include_router(generator_router, tags=["Generator"])
