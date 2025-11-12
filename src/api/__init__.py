from fastapi import APIRouter
from .signals import router as signals_router
from .reports import router as reports_router

api_router = APIRouter()

api_router.include_router(signals_router)
api_router.include_router(reports_router)

__all__ = ["api_router"]