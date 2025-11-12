from fastapi import APIRouter, Query
from typing import Optional
from ..schemas import ApiResponse, AnalysisResult, SignalsQueryParams
from ..services.mock_data import generate_mock_analysis

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("", response_model=ApiResponse[AnalysisResult])
async def get_signals(
    sector: Optional[str] = Query(None, description="섹터 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수")
):
    """
    최신 트레이딩 시그널 조회
    
    - **sector**: 섹터 필터 (IT, 통신서비스, 임의소비재 등)
    - **limit**: 반환할 시그널 개수 (기본: 20)
    """
    
    try:
        data = generate_mock_analysis(limit=limit, sector=sector)
        return ApiResponse(success=True, data=data)
    except Exception as e:
        return ApiResponse(success=False, data={}, error=str(e))