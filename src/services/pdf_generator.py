from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io
import os
from typing import Dict, Any

# 한글 폰트 등록
def register_korean_fonts():
    """한글 폰트 등록"""
    try:
        # 폰트 파일 경로
        font_path = os.path.join(os.path.dirname(__file__), '../../fonts')
        
        # 나눔고딕 등록
        pdfmetrics.registerFont(
            TTFont('NanumGothic', os.path.join(font_path, 'NanumGothic-Regular.ttf'))
        )
        pdfmetrics.registerFont(
            TTFont('NanumGothic-Bold', os.path.join(font_path, 'NanumGothic-Bold.ttf'))
        )
        
        return True
    except Exception as e:
        print(f"Font registration error: {e}")
        return False


def generate_report_pdf(report_data: Dict[str, Any]) -> bytes:
    """
    리포트 PDF 생성
    
    Args:
        report_data: 리포트 데이터 딕셔너리
        
    Returns:
        PDF 바이트 데이터
    """
    # 한글 폰트 등록
    register_korean_fonts()
    
    # PDF 메모리 버퍼
    buffer = io.BytesIO()
    
    # PDF 문서 설정
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    
    # 스토리 (페이지 콘텐츠)
    story = []
    
    # 스타일 정의
    styles = getSampleStyleSheet()
    
    # 커스텀 스타일 (한글 폰트 적용)
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#4c6fff'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='NanumGothic-Bold',
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a1f3a'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='NanumGothic-Bold',
    )
    
    # 1. 제목
    date_str = datetime.fromisoformat(report_data['date']).strftime('%Y년 %m월')
    title = Paragraph(f"<b>StockPlay Monthly Report</b><br/>{date_str}", title_style)
    story.append(title)
    story.append(Spacer(1, 0.3 * inch))
    
    # 2. 백테스트 성과
    story.append(Paragraph("📈 백테스트 성과 (2020-2024)", heading_style))
    
    performance = report_data['analysisResult']['performance']
    perf_data = [
        ['지표', '값'],
        ['평균 수익률', f"+{performance['avgReturn']}%"],
        ['승률', f"{performance['winRate']}%"],
        ['Sharpe Ratio', f"{performance['sharpeRatio']}"],
        ['최대 낙폭', f"{performance['maxDrawdown']}%"],
    ]
    
    perf_table = Table(perf_data, colWidths=[3 * inch, 3 * inch])
    perf_table.setStyle(TableStyle([
        # 헤더
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),  # 한글 폰트
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # 데이터
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),  # 한글 폰트
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # 테두리
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(perf_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # 3. Top 5 추천 종목
    story.append(Paragraph("🎯 Top 5 추천 종목", heading_style))
    
    top_picks = report_data['analysisResult']['topPicks'][:5]
    picks_data = [['순위', '종목', '회사명', '섹터', '예상 수익률']]
    
    for idx, signal in enumerate(top_picks, 1):
        picks_data.append([
            str(idx),
            signal['symbol'],
            signal['companyName'][:20] + '...' if len(signal['companyName']) > 20 else signal['companyName'],
            signal['sector'],
            f"+{signal['expectedReturn']}%"
        ])
    
    picks_table = Table(
        picks_data,
        colWidths=[0.6 * inch, 0.8 * inch, 2.2 * inch, 1.2 * inch, 1.2 * inch]
    )
    picks_table.setStyle(TableStyle([
        # 헤더
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),  # 한글 폰트
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # 데이터
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),  # 한글 폰트
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # 순위 강조
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e8eeff')),
        ('FONTNAME', (0, 1), (0, -1), 'NanumGothic-Bold'),
        
        # 테두리
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(picks_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # 4. 섹터별 분석
    story.append(Paragraph("📊 섹터별 분석", heading_style))
    
    sectors = report_data['analysisResult']['sectorAnalysis']
    sector_data = [['섹터', 'YoY 평균', 'MoM 평균', '시그널 수']]
    
    for sector in sectors:
        sector_data.append([
            sector['sector'],
            f"+{sector['avgYoYGrowth']}%",
            f"+{sector['avgMoMGrowth']}%",
            f"{sector['signalCount']}개"
        ])
    
    sector_table = Table(
        sector_data,
        colWidths=[2 * inch, 1.5 * inch, 1.5 * inch, 1 * inch]
    )
    sector_table.setStyle(TableStyle([
        # 헤더
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),  # 한글 폰트
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # 데이터
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),  # 한글 폰트
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # 테두리
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(sector_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # 5. 푸터
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='NanumGothic',  # 한글 폰트
    )
    
    created_date = datetime.fromisoformat(report_data['createdAt']).strftime('%Y년 %m월 %d일')
    footer_text = f"""
    <br/><br/>
    생성일: {created_date}<br/>
    <br/>
    ⚠️ 본 리포트는 투자 참고 자료이며, 투자 판단 및 결과에 대한 책임은 투자자 본인에게 있습니다.<br/>
    StockPlay는 데이터 분석을 제공할 뿐, 투자 손실에 대한 책임을 지지 않습니다.
    """
    
    story.append(Paragraph(footer_text, footer_style))
    
    # PDF 빌드
    doc.build(story)
    
    # 버퍼 포인터를 처음으로 되돌림
    buffer.seek(0)
    
    return buffer.getvalue()


def save_pdf_locally(pdf_bytes: bytes, filename: str) -> str:
    """
    로컬 파일로 PDF 저장 (개발/테스트용)
    
    Args:
        pdf_bytes: PDF 바이트 데이터
        filename: 저장할 파일명
        
    Returns:
        저장된 파일 경로
    """
    filepath = f"data/reports/{filename}"
    
    # 디렉토리 생성
    import os
    os.makedirs("data/reports", exist_ok=True)
    
    # 파일 저장
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)
    
    return filepath


def upload_to_s3(pdf_bytes: bytes, filename: str, bucket_name: str = 'stockplay-reports') -> str:
    """
    S3에 PDF 업로드 (프로덕션용)
    
    Args:
        pdf_bytes: PDF 바이트 데이터
        filename: S3 객체 키
        bucket_name: S3 버킷 이름
        
    Returns:
        S3 URL
    """
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        s3 = boto3.client('s3')
        
        # S3 업로드
        s3.put_object(
            Bucket=bucket_name,
            Key=f"reports/{filename}",
            Body=pdf_bytes,
            ContentType='application/pdf',
            ContentDisposition=f'attachment; filename="{filename}"'
        )
        
        # 퍼블릭 URL 생성
        url = f"https://{bucket_name}.s3.amazonaws.com/reports/{filename}"
        
        return url
        
    except ClientError as e:
        print(f"S3 upload error: {e}")
        raise