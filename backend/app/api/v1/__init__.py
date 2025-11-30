"""API v1 routes"""

from fastapi import APIRouter

from .search import router as search_router
from .analysis import router as analysis_router
from .cases import router as cases_router
from .export import router as export_router
from .reference import router as reference_router

router = APIRouter(prefix="/api/v1")

router.include_router(search_router, tags=["Search"])
router.include_router(analysis_router, tags=["Analysis"])
router.include_router(cases_router, tags=["Cases"])
router.include_router(export_router, tags=["Export"])
router.include_router(reference_router, tags=["Reference"])
