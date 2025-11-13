"""
리포트 API (Dashboard 간단 PDF / Reports 상세 PDF 구분)
"""

from fastapi import APIRouter, Query, Body
from typing import Optional
from ..schemas import ApiResponse, ReportsResponse, DownloadResponse
from ..services.mock_data import generate_mock_reports
from ..services.pdf_generator import (
    generate_dashboard_pdf, 
    generate_full_report_pdf, 
    generate_report_pdf,
    save_pdf_locally, 
    upload_to_s3
)
from ..config import settings
import uuid
from datetime import datetime

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
        return ApiResponse(
            success=False, 
            data={"reports": [], "total": 0, "hasMore": False}, 
            error=str(e)
        )


@router.get("/{report_id}/download", response_model=ApiResponse[DownloadResponse])
async def get_report_download_url(report_id: str):
    """
    PDF 다운로드 URL 생성
    
    - **report_id**: 리포트 ID
    """
    
    try:
        bucket_name = settings.S3_BUCKET_NAME
        region = settings.AWS_REGION
        
        url = f"https://{bucket_name}.s3.{region}.amazonaws.com/reports/{report_id}.pdf"
        
        return ApiResponse(
            success=True,
            data={"url": url, "expiresIn": 3600}
        )
    except Exception as e:
        return ApiResponse(
            success=False, 
            data={"url": "", "expiresIn": 0}, 
            error=str(e)
        )


@router.post("/generate-dashboard")
async def generate_dashboard_pdf_endpoint(
    signal_data: dict = Body(...)
):
    """
    Dashboard용 간단 PDF 생성 (차트 포함, AI 없음)
    
    Request Body:
    {
        "symbol": "AAPL",
        "sector": "IT",
        "signalType": "BUY",
        "period": "5d",
        "expectedReturn": 12.5,
        "vsKospi": 10.3,
        "kospiReturn": 2.2,
        "surpriseZ": 2.52,
        "yoyGrowth": 18.3,
        "confidenceScore": 85
    }
    """
    
    try:
        # PDF 생성
        pdf_bytes = generate_dashboard_pdf(signal_data)
        
        # 파일명
        symbol = signal_data.get('symbol', 'UNKNOWN')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dashboard_{symbol}_{timestamp}.pdf"
        
        # 환경에 따라 로컬 저장 또는 S3 업로드
        if settings.DEBUG:
            filepath = save_pdf_locally(pdf_bytes, filename)
            url = f"/data/reports/{filename}"
            message = "Dashboard PDF generated and saved locally"
        else:
            url = upload_to_s3(
                pdf_bytes, 
                filename, 
                bucket_name=settings.S3_BUCKET_NAME
            )
            message = "Dashboard PDF generated and uploaded to S3"
        
        return ApiResponse(
            success=True,
            data={
                "url": url,
                "filename": filename,
                "message": message
            }
        )
        
    except Exception as e:
        print(f"Dashboard PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(
            success=False,
            data={"url": "", "filename": "", "message": ""},
            error=str(e)
        )


@router.post("/generate-full")
async def generate_full_report_endpoint(
    signal_data: dict = Body(...),
    use_ai: bool = Query(False, description="AI 분석 사용 여부")
):
    """
    Reports용 상세 PDF 생성 (차트 + AI 분석 포함)
    
    Request Body: (Dashboard와 동일)
    
    Query Parameters:
    - **use_ai**: AI 분석 포함 여부 (default: False)
    """
    
    try:
        ai_analysis = None
        
        # AI 분석 (선택적)
        if use_ai:
            try:
                ai_analysis = await generate_ai_analysis(signal_data)
            except Exception as ai_error:
                print(f"AI analysis failed, continuing without AI: {ai_error}")
                ai_analysis = None
        
        # PDF 생성
        pdf_bytes = generate_full_report_pdf(signal_data, ai_analysis)
        
        # 파일명
        symbol = signal_data.get('symbol', 'UNKNOWN')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"report_{symbol}_{timestamp}.pdf"
        
        # 환경에 따라 로컬 저장 또는 S3 업로드
        if settings.DEBUG:
            filepath = save_pdf_locally(pdf_bytes, filename)
            url = f"/data/reports/{filename}"
            message = "Full report PDF generated and saved locally"
        else:
            url = upload_to_s3(
                pdf_bytes, 
                filename, 
                bucket_name=settings.S3_BUCKET_NAME
            )
            message = "Full report PDF generated and uploaded to S3"
        
        return ApiResponse(
            success=True,
            data={
                "url": url,
                "filename": filename,
                "message": message,
                "ai_used": use_ai and ai_analysis is not None
            }
        )
        
    except Exception as e:
        print(f"Full report PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(
            success=False,
            data={"url": "", "filename": "", "message": "", "ai_used": False},
            error=str(e)
        )


async def generate_ai_analysis(signal_data: dict) -> dict:
    """
    Claude API를 사용한 AI 분석 생성
    
    Args:
        signal_data: 시그널 데이터
        
    Returns:
        AI 분석 결과 dict
    """
    try:
        import os
        from anthropic import Anthropic
        
        # API 키 확인
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("⚠️ ANTHROPIC_API_KEY not found")
            return None
        
        client = Anthropic(api_key=api_key)
        
        # 프롬프트 생성
        signal_type_kr = {
            'BUY': '매수',
            'HOLD': '홀드',
            'SELL': '매도'
        }.get(signal_data.get('signalType', 'BUY'), '매수')
        
        prompt = f"""
다음 주식 데이터를 분석하여 투자 리포트를 작성해주세요:

**종목 정보:**
- 종목: {signal_data.get('symbol', 'N/A')}
- 섹터: {signal_data.get('sector', 'N/A')}
- 시그널: {signal_type_kr}
- 예측 기간: {signal_data.get('period', '1d')}

**성과 지표:**
- 예상 수익률: {signal_data.get('expectedReturn', 0):.1f}%
- KOSPI 대비: {signal_data.get('vsKospi', 0):.1f}%
- KOSPI 수익률: {signal_data.get('kospiReturn', 0):.1f}%
- Surprise Z-Score: {signal_data.get('surpriseZ', 0):.2f}
- 신뢰도: {signal_data.get('confidenceScore', 0):.0f}%
- YoY 성장률: {signal_data.get('yoyGrowth', 0):.1f}%

다음 4개 섹션으로 분석해주세요:

1. **종목 개요** (2-3문장): 종목의 현재 상황과 주요 특징
2. **투자 의견** (3-4문장): 수익률 전망과 투자 포지션 추천
3. **리스크 분석** (2-3문장): 주요 리스크 요인
4. **기술적 분석** (2-3문장): Surprise 지표 및 기술적 관점

각 섹션은 명확하고 전문적으로 작성해주세요.
"""
        
        # Claude API 호출
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # 응답 파싱
        full_text = message.content[0].text
        
        # 간단한 섹션 분리 (실제로는 더 정교하게 파싱 필요)
        sections = {
            'overview': '',
            'investment_opinion': '',
            'risk_analysis': '',
            'technical_analysis': ''
        }
        
        # 전체 텍스트를 각 섹션에 분배 (간단 버전)
        lines = full_text.split('\n')
        current_section = 'overview'
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '투자 의견' in line or 'investment' in line.lower():
                current_section = 'investment_opinion'
                continue
            elif '리스크' in line or 'risk' in line.lower():
                current_section = 'risk_analysis'
                continue
            elif '기술적' in line or 'technical' in line.lower():
                current_section = 'technical_analysis'
                continue
            
            sections[current_section] += line + '<br/>'
        
        print(f"✅ AI 분석 생성 완료")
        return sections
        
    except Exception as e:
        print(f"❌ AI 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


@router.post("/{report_id}/generate-pdf")
async def generate_pdf(report_id: str):
    """
    기존 월간 리포트 PDF 생성 (하위 호환성 유지)
    
    - **report_id**: 리포트 ID
    """
    
    try:
        reports_data = generate_mock_reports(limit=10, offset=0)
        
        report = next((r for r in reports_data['reports'] if r['id'] == report_id), None)
        
        if not report:
            return ApiResponse(
                success=False,
                data={"url": "", "message": ""},
                error="Report not found"
            )
        
        pdf_bytes = generate_report_pdf(report)
        
        filename = f"{report_id}.pdf"
        
        if settings.DEBUG:
            filepath = save_pdf_locally(pdf_bytes, filename)
            url = f"/data/reports/{filename}"
            message = "PDF generated and saved locally"
        else:
            url = upload_to_s3(
                pdf_bytes, 
                filename, 
                bucket_name=settings.S3_BUCKET_NAME
            )
            message = "PDF generated and uploaded to S3"
        
        return ApiResponse(
            success=True,
            data={
                "url": url,
                "message": message
            }
        )
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        return ApiResponse(
            success=False,
            data={"url": "", "message": ""},
            error=str(e)
        )