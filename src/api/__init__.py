from fastapi import APIRouter
from .signals import router as signals_router
from .reports import router as reports_router
from .subscribe import router as subscribe_router
from .predict import router as predict_router

api_router = APIRouter()

api_router.include_router(signals_router)
api_router.include_router(reports_router)
api_router.include_router(subscribe_router)
api_router.include_router(predict_router)

__all__ = ["api_router"]