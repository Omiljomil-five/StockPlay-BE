from fastapi import APIRouter, Query
from ..schemas import ApiResponse, ReportsResponse, DownloadResponse
from ..services.mock_data import generate_mock_reports

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("", response_model=ApiResponse[ReportsResponse])
async def get_reports(
    limit: int = Query(10, ge=1, le=50, description="페이지 크기"),
    offset: int = Query(0, ge=0, description="페이지 오프셋")
):
    """
    과거 리포트 목록 조회
    
    - **limit**: 페이지당 리포트 수
    - **offset**: 시작 위치
    """
    
    try:
        data = generate_mock_reports(limit=limit, offset=offset)
        return ApiResponse(success=True, data=data)
    except Exception as e:
        return ApiResponse(success=False, data={"reports": [], "total": 0, "hasMore": False}, error=str(e))

@router.get("/{report_id}/download", response_model=ApiResponse[DownloadResponse])
async def get_report_download_url(report_id: str):
    """
    PDF 다운로드 URL 생성
    
    - **report_id**: 리포트 ID
    """
    
    try:
        # Mock URL
        url = f"https://stockplay-reports.s3.amazonaws.com/{report_id}.pdf"
        return ApiResponse(
            success=True,
            data={"url": url, "expiresIn": 3600}
        )
    except Exception as e:
        return ApiResponse(success=False, data={"url": "", "expiresIn": 0}, error=str(e))