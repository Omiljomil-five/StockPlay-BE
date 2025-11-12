from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import api_router

app = FastAPI(
    title="StockPlay API",
    description="수출 데이터 기반 주식 트레이딩 시그널 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_PREFIX)

# Health Check
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "message": "StockPlay API is running",
    }

# Root
@app.get("/")
async def root():
    return {
        "message": "Welcome to StockPlay API",
        "docs": "/docs",
        "health": "/api/health",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )