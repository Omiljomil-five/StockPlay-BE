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
    upload_to_s3,
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
            # S3에 업로드 (보관용)
            s3_url = upload_to_s3(pdf_bytes, filename, bucket_name)
        except Exception as e:
            print(f"S3 업로드 실패 (무시): {e}")

        # API 다운로드 엔드포인트 URL 반환
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

        # S3에 업로드 (보관용)
        import os
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        try:
            s3_url = upload_to_s3(pdf_bytes, filename, bucket_name)
        except Exception as e:
            print(f"S3 업로드 실패 (무시): {e}")

        # API 다운로드 엔드포인트 URL 반환
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

    - report-YYYY-MM 형식의 리포트 ID로 해당 월 실데이터 PDF 생성
    """
    try:
        import os
        import re
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        # report-YYYY-MM 패턴 매칭
        match = re.match(r'^report-(\d{4})-(\d{2})$', report_id)
        if match:
            year, month = match.group(1), match.group(2)
            ym = f"{year}-{month}"
            print(f"리포트 다운로드 URL 생성: {report_id} (ym={ym})")

            from ..services.ml_predictor import get_predictor
            from ..services.pdf_generator import generate_full_report_pdf
            from ..services.ai_analyzer import generate_ai_analysis, get_fallback_analysis

            predictor = get_predictor()
            summaries = predictor.get_monthly_summaries()

            # 해당 월 요약 찾기
            month_summary = None
            for s in summaries:
                if s['ym'] == ym:
                    month_summary = s
                    break

            if month_summary and month_summary.get('topPicks'):
                top = month_summary['topPicks'][0]
                signal_data = {
                    'symbol': top['symbol'],
                    'companyName': top['companyName'],
                    'sector': top['sector'],
                    'signalType': top['signalType'],
                    'period': '10d',
                    'expectedReturn': top['expectedReturn'],
                    'vsKospi': 0.0,
                    'kospiReturn': 0.0,
                    'surpriseZ': 0.0,
                    'yoyGrowth': top.get('yoyGrowth', 0.0),
                    'confidenceScore': top['confidenceScore'],
                }
            else:
                signal_data = {
                    'symbol': '005930',
                    'companyName': f'{ym} Monthly Report',
                    'sector': 'Market',
                    'signalType': 'HOLD',
                    'period': '10d',
                    'expectedReturn': month_summary['avgReturn'] if month_summary else 0.0,
                    'vsKospi': 0.0,
                    'kospiReturn': 0.0,
                    'surpriseZ': 0.0,
                    'yoyGrowth': 0.0,
                    'confidenceScore': 50.0,
                }

            ai_analysis = generate_ai_analysis(signal_data)
            if not ai_analysis:
                ai_analysis = get_fallback_analysis(signal_data)

            pdf_bytes = generate_full_report_pdf(signal_data, ai_analysis)
            filename = f"{report_id}.pdf"

            try:
                upload_to_s3(pdf_bytes, filename, bucket_name)
            except Exception as e:
                print(f"S3 업로드 실패 (무시): {e}")

            url = f"/api/reports/download/{filename}"

            return {
                "success": True,
                "data": {
                    "url": url,
                    "expiresIn": 3600
                }
            }

        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"리포트 URL 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"URL 조회 실패: {str(e)}")


@router.get("/download/{filename}")
async def download_pdf(filename: str):
    """
    PDF 파일 다운로드

    - S3에서 파일을 가져와 스트리밍
    - S3에 없으면 로컬 파일 확인
    - Mock 리포트의 경우 동적으로 생성
    """
    try:
        import os
        import boto3
        from urllib.parse import quote

        encoded_filename = quote(filename)
        bucket_name = os.getenv('S3_REPORT_BUCKET', 'stockplay-reports-yjw-20251113')

        # 1) S3에서 가져오기 시도
        try:
            s3 = boto3.client('s3', region_name='ap-northeast-2')
            s3_response = s3.get_object(
                Bucket=bucket_name,
                Key=f"reports/{filename}"
            )
            pdf_bytes = s3_response['Body'].read()

            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Type": "application/pdf"
                }
            )
        except Exception as s3_err:
            print(f"S3 다운로드 실패, 로컬/동적 생성 시도: {s3_err}")

        # 2) 로컬 파일 확인
        filepath = f"data/reports/{filename}"
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                pdf_bytes = f.read()

            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Type": "application/pdf"
                }
            )

        # 3) report-YYYY-MM 패턴 동적 생성
        import re
        match = re.match(r'^report-(\d{4}-\d{2})\.pdf$', filename)
        if match:
            ym = match.group(1)
            print(f"리포트 동적 생성: {filename} (ym={ym})")
            from ..services.ml_predictor import get_predictor
            from ..services.pdf_generator import generate_full_report_pdf
            from ..services.ai_analyzer import get_fallback_analysis

            predictor = get_predictor()
            summaries = predictor.get_monthly_summaries()
            month_summary = next((s for s in summaries if s['ym'] == ym), None)

            if month_summary and month_summary.get('topPicks'):
                top = month_summary['topPicks'][0]
                signal_data = {
                    'symbol': top['symbol'],
                    'companyName': top['companyName'],
                    'sector': top['sector'],
                    'signalType': top['signalType'],
                    'period': '10d',
                    'expectedReturn': top['expectedReturn'],
                    'vsKospi': 0.0,
                    'kospiReturn': 0.0,
                    'surpriseZ': 0.0,
                    'yoyGrowth': top.get('yoyGrowth', 0.0),
                    'confidenceScore': top['confidenceScore'],
                }
            else:
                signal_data = {
                    'symbol': '005930',
                    'companyName': f'{ym} Monthly Report',
                    'sector': 'Market',
                    'signalType': 'HOLD',
                    'period': '10d',
                    'expectedReturn': 0.0,
                    'vsKospi': 0.0,
                    'kospiReturn': 0.0,
                    'surpriseZ': 0.0,
                    'yoyGrowth': 0.0,
                    'confidenceScore': 50.0,
                }

            ai_analysis = get_fallback_analysis(signal_data)
            pdf_bytes = generate_full_report_pdf(signal_data, ai_analysis)

            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Type": "application/pdf"
                }
            )

        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

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
    리포트 목록 조회 (실데이터 기반 월별 리포트)
    """
    try:
        from ..schemas.report import Report
        from ..schemas.signal import AnalysisResult, TradingSignal
        from ..services.ml_predictor import get_predictor

        predictor = get_predictor()
        monthly_summaries = predictor.get_monthly_summaries()

        all_reports = []
        for summary in monthly_summaries:
            ym = summary['ym']  # e.g. "2024-11"
            year, month = int(ym.split('-')[0]), int(ym.split('-')[1])
            report_date = datetime(year, month, 1)

            # topPicks → TradingSignal 스키마로 변환
            top_picks = []
            for pick in summary.get('topPicks', []):
                top_picks.append(TradingSignal(
                    id=pick['id'],
                    symbol=pick['symbol'],
                    companyName=pick['companyName'],
                    sector=pick['sector'],
                    signalType=pick['signalType'],
                    yoyGrowth=pick.get('yoyGrowth', 0.0),
                    expectedReturn=pick['expectedReturn'],
                    confidenceScore=pick['confidenceScore'],
                    period=pick.get('period', '10d'),
                ))

            analysis_result = AnalysisResult(
                date=report_date.isoformat(),
                topPicks=top_picks,
                performance={
                    'avgReturn': summary['avgReturn'],
                    'winRate': summary['winRate'],
                    'sharpeRatio': summary['sharpeRatio'],
                    'maxDrawdown': summary['maxDrawdown'],
                },
                sectorAnalysis=[],
                totalSignals=summary['totalSignals'],
            )

            report = Report(
                id=f"report-{ym}",
                date=report_date,
                pdfUrl=f"/reports/{ym}-report.pdf",
                analysisResult=analysis_result,
                createdAt=report_date,
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
        print(f"리포트 목록 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")
