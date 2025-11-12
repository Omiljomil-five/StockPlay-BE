from fastapi import APIRouter, Query
from ..schemas import ApiResponse, ReportsResponse, DownloadResponse
from ..services.mock_data import generate_mock_reports
from ..services.pdf_generator import generate_report_pdf, save_pdf_locally

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
        url = f"https://stockplay-reports.s3.amazonaws.com/reports/{report_id}.pdf"
        return ApiResponse(
            success=True,
            data={"url": url, "expiresIn": 3600}
        )
    except Exception as e:
        return ApiResponse(success=False, data={"url": "", "expiresIn": 0}, error=str(e))


@router.post("/{report_id}/generate-pdf")
async def generate_pdf(report_id: str):
    """
    리포트 PDF 생성
    
    - **report_id**: 리포트 ID
    """
    
    try:
        # Mock 리포트 데이터 조회
        from ..services.mock_data import generate_mock_reports
        reports_data = generate_mock_reports(limit=10, offset=0)
        
        # 해당 리포트 찾기
        report = next((r for r in reports_data['reports'] if r['id'] == report_id), None)
        
        if not report:
            return ApiResponse(
                success=False,
                data={"url": "", "message": ""},
                error="Report not found"
            )
        
        # PDF 생성
        pdf_bytes = generate_report_pdf(report)
        
        # 로컬 저장 (개발용)
        filename = f"{report_id}.pdf"
        filepath = save_pdf_locally(pdf_bytes, filename)
        
        # TODO: 프로덕션에서는 S3 업로드
        # from ..services.pdf_generator import upload_to_s3
        # url = upload_to_s3(pdf_bytes, filename)
        
        return ApiResponse(
            success=True,
            data={
                "url": f"/data/reports/{filename}",
                "message": "PDF generated successfully"
            }
        )
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        return ApiResponse(
            success=False,
            data={"url": "", "message": ""},
            error=str(e)
        )