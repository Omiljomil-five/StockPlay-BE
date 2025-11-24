from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional
import io
from ..schemas.common import ApiResponse
from ..schemas.report import (
    PdfGenerationRequest,
    PdfGenerationResponse,
    ReportsQueryParams,
    ReportsResponse
)
from ..services.pdf_generator import (
    generate_dashboard_pdf,
    generate_full_report_pdf,
    save_pdf_locally,
    upload_to_s3,
    get_s3_presigned_url
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=ApiResponse[PdfGenerationResponse])
async def generate_pdf(request: PdfGenerationRequest):
    """
    대시보드용 전문 리포트 PDF 생성 (AI 분석 + KOSPI 차트 포함)

    - 시그널 카드 데이터를 기반으로 전문 리포트 생성
    - Claude AI 분석 포함 (선택적)
    - KOSPI 기술적 분석 차트 포함
    """
    try:
        from ..services.ai_analyzer import generate_ai_analysis, get_fallback_analysis

        # companyName이 없으면 자동 생성
        company_name = request.companyName or f"{request.sector} 종목 {request.symbol}"

        # 요청 데이터를 딕셔너리로 변환
        signal_data = {
            'symbol': request.symbol,
            'companyName': company_name,
            'sector': request.sector,
            'signalType': request.signalType,
            'period': request.period,
            'expectedReturn': request.expectedReturn,
            'vsKospi': request.vsKospi,
            'kospiReturn': request.kospiReturn,
            'surpriseZ': request.surpriseZ,
            'yoyGrowth': request.yoyGrowth,
            'confidenceScore': request.confidenceScore
        }

        # AI 분석 생성 (실패 시 fallback)
        ai_analysis = generate_ai_analysis(signal_data)
        if not ai_analysis:
            ai_analysis = get_fallback_analysis(signal_data)

        # 전문 리포트 PDF 생성
        pdf_bytes = generate_full_report_pdf(signal_data, ai_analysis)

        # 파일명 생성 (티커 심볼 사용)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"stockplay_signal_{request.symbol}_{timestamp}.pdf"

        # S3에 업로드 및 presigned URL 생성
        import os
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        try:
            # S3에 업로드
            s3_url = upload_to_s3(pdf_bytes, filename, bucket_name)

            # presigned URL 생성 (1시간 유효)
            url = get_s3_presigned_url(bucket_name, f"reports/{filename}", expiration=3600)
        except Exception as e:
            print(f"S3 업로드 실패, 로컬 저장으로 폴백: {e}")
            # S3 실패 시 로컬에 저장
            filepath = save_pdf_locally(pdf_bytes, filename)
            url = f"/api/reports/download/{filename}"

        response_data = PdfGenerationResponse(
            url=url,
            filename=filename,
            message="PDF가 성공적으로 생성되었습니다.",
            ai_used=False
        )

        return ApiResponse(success=True, data=response_data)

    except Exception as e:
        print(f"❌ PDF 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF 생성 실패: {str(e)}")


@router.post("/generate-full", response_model=ApiResponse[PdfGenerationResponse])
async def generate_full_pdf(
    request: PdfGenerationRequest,
    use_ai: bool = False
):
    """
    상세 리포트 PDF 생성 (AI 분석 포함 옵션)

    - AI 분석이 포함된 상세 리포트 생성
    - use_ai=true로 설정 시 AI 분석 추가
    """
    try:
        # companyName이 없으면 자동 생성
        company_name = request.companyName or f"{request.sector} 종목 {request.symbol}"

        # 요청 데이터를 딕셔너리로 변환
        signal_data = {
            'symbol': request.symbol,
            'companyName': company_name,
            'sector': request.sector,
            'signalType': request.signalType,
            'period': request.period,
            'expectedReturn': request.expectedReturn,
            'vsKospi': request.vsKospi,
            'kospiReturn': request.kospiReturn,
            'surpriseZ': request.surpriseZ,
            'yoyGrowth': request.yoyGrowth,
            'confidenceScore': request.confidenceScore
        }

        # AI 분석 (선택적)
        ai_analysis = None
        if use_ai:
            # TODO: AI 분석 서비스 연동
            ai_analysis = {
                'overview': f"{company_name}({request.symbol}) 종목에 대한 AI 분석 결과입니다.",
                'investment_opinion': "현재 시장 상황을 고려할 때 긍정적입니다.",
                'risk_analysis': "주요 리스크 요인을 모니터링하고 있습니다.",
                'technical_analysis': "기술적 지표가 양호합니다."
            }

        # 상세 PDF 생성
        pdf_bytes = generate_full_report_pdf(signal_data, ai_analysis)

        # 파일명 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"stockplay_report_{request.symbol}_{timestamp}.pdf"

        # S3에 업로드 및 presigned URL 생성
        import os
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        try:
            # S3에 업로드
            s3_url = upload_to_s3(pdf_bytes, filename, bucket_name)

            # presigned URL 생성 (1시간 유효)
            url = get_s3_presigned_url(bucket_name, f"reports/{filename}", expiration=3600)
        except Exception as e:
            print(f"S3 업로드 실패, 로컬 저장으로 폴백: {e}")
            # S3 실패 시 로컬에 저장
            filepath = save_pdf_locally(pdf_bytes, filename)
            url = f"/api/reports/download/{filename}"

        response_data = PdfGenerationResponse(
            url=url,
            filename=filename,
            message="상세 리포트가 성공적으로 생성되었습니다.",
            ai_used=use_ai
        )

        return ApiResponse(success=True, data=response_data)

    except Exception as e:
        print(f"❌ 상세 리포트 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"리포트 생성 실패: {str(e)}")


@router.get("/{report_id}/download")
async def get_report_download_url(report_id: str):
    """
    리포트 다운로드 URL 조회 (Reports 페이지용)

    - report-2024-XX 형식의 리포트 ID를 받아 presigned URL 생성
    - Mock 리포트의 경우 동적으로 PDF 생성하고 S3 업로드
    """
    try:
        import os
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        # Mock 리포트인 경우 (report-2024-XX)
        if report_id.startswith('report-2024-'):
            print(f"📄 Mock 리포트 다운로드 URL 생성: {report_id}")

            # Mock 데이터로 PDF 생성 (고퀄리티 리포트 사용)
            from ..services.pdf_generator import generate_full_report_pdf
            from ..services.ai_analyzer import generate_ai_analysis, get_fallback_analysis

            mock_signal = {
                'symbol': 'MOCK-001',
                'companyName': '샘플 종목',
                'sector': 'IT',
                'signalType': 'BUY',
                'period': '1d',
                'expectedReturn': 11.2,
                'vsKospi': 9.2,
                'kospiReturn': 2.0,
                'surpriseZ': 2.5,
                'yoyGrowth': 18.5,
                'confidenceScore': 85.0
            }

            # AI 분석 시도 (실패 시 fallback)
            ai_analysis = generate_ai_analysis(mock_signal)
            if not ai_analysis:
                ai_analysis = get_fallback_analysis(mock_signal)

            pdf_bytes = generate_full_report_pdf(mock_signal, ai_analysis)
            filename = f"{report_id}.pdf"

            # S3에 업로드
            try:
                s3_url = upload_to_s3(pdf_bytes, filename, bucket_name)
                # presigned URL 생성 (1시간 유효)
                url = get_s3_presigned_url(bucket_name, f"reports/{filename}", expiration=3600)
            except Exception as e:
                print(f"S3 업로드 실패, 로컬 저장으로 폴백: {e}")
                # S3 실패 시 로컬에 저장
                filepath = save_pdf_locally(pdf_bytes, filename)
                url = f"/api/reports/download/{filename}"

            return {
                "success": True,
                "data": {
                    "url": url,
                    "expiresIn": 3600
                }
            }

        # 실제 파일이 있는 경우
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 리포트 URL 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"URL 조회 실패: {str(e)}")


@router.get("/download/{filename}")
async def download_pdf(filename: str):
    """
    PDF 파일 다운로드 (로컬 폴백용)

    - 생성된 PDF 파일을 다운로드
    - Mock 리포트의 경우 동적으로 생성
    """
    try:
        import os
        filepath = f"data/reports/{filename}"

        # 파일 존재 확인
        if not os.path.exists(filepath):
            # Mock 리포트인 경우 (report-2024-XX.pdf) 동적 생성
            if filename.startswith('report-2024-'):
                print(f"📄 Mock 리포트 동적 생성: {filename}")

                # Mock 데이터로 PDF 생성
                from ..services.pdf_generator import generate_dashboard_pdf

                mock_signal = {
                    'symbol': 'MOCK-001',
                    'companyName': '샘플 종목',
                    'sector': 'IT',
                    'signalType': 'BUY',
                    'period': '1d',
                    'expectedReturn': 11.2,
                    'vsKospi': 9.2,
                    'kospiReturn': 2.0,
                    'surpriseZ': 2.5,
                    'yoyGrowth': 18.5,
                    'confidenceScore': 85.0
                }

                pdf_bytes = generate_dashboard_pdf(mock_signal)

                # StreamingResponse로 반환
                from urllib.parse import quote
                encoded_filename = quote(filename)

                return StreamingResponse(
                    io.BytesIO(pdf_bytes),
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                        "Content-Type": "application/pdf"
                    }
                )

            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        # 파일 읽기
        with open(filepath, 'rb') as f:
            pdf_bytes = f.read()

        # StreamingResponse로 반환
        from urllib.parse import quote
        encoded_filename = quote(filename)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "application/pdf"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ PDF 다운로드 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"다운로드 실패: {str(e)}")


@router.get("", response_model=ApiResponse[ReportsResponse])
async def get_reports(
    limit: int = 10,
    offset: int = 0
):
    """
    리포트 목록 조회

    - 2024년 6월~12월 리포트 목록 반환
    """
    try:
        from ..schemas.report import Report
        from ..schemas.signal import AnalysisResult

        # 2024년 6월~12월 Mock 리포트 생성
        all_reports = []
        for month in range(12, 5, -1):  # 12월부터 6월까지 역순
            report_date = datetime(2024, month, 1)

            # Mock 분석 결과
            analysis_result = AnalysisResult(
                date=report_date.isoformat(),
                topPicks=[],
                performance={
                    'avgReturn': 11.2,
                    'winRate': 75.3,
                    'sharpeRatio': 1.8,
                    'maxDrawdown': -8.5
                },
                sectorAnalysis=[],
                totalSignals=20
            )

            report = Report(
                id=f"report-2024-{month:02d}",
                date=report_date,
                pdfUrl=f"/reports/2024-{month:02d}-report.pdf",
                analysisResult=analysis_result,
                createdAt=report_date
            )
            all_reports.append(report)

        total = len(all_reports)

        # 페이지네이션
        paginated_reports = all_reports[offset:offset + limit]
        has_more = (offset + limit) < total

        response_data = ReportsResponse(
            reports=paginated_reports,
            total=total,
            hasMore=has_more
        )

        return ApiResponse(success=True, data=response_data)

    except Exception as e:
        print(f"❌ 리포트 목록 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")
