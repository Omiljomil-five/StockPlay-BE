from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io
import os
from typing import Dict, Any, Optional


# 한글 폰트 등록 (캐싱)
_fonts_registered = False
_logo_bytes = None

def register_korean_fonts():
    """한글 폰트 등록 (한 번만 실행)"""
    global _fonts_registered

    if _fonts_registered:
        return True

    try:
        font_path = os.path.join(os.path.dirname(__file__), '../../fonts')

        pdfmetrics.registerFont(
            TTFont('NanumGothic', os.path.join(font_path, 'NanumGothic-Regular.ttf'))
        )
        pdfmetrics.registerFont(
            TTFont('NanumGothic-Bold', os.path.join(font_path, 'NanumGothic-Bold.ttf'))
        )

        _fonts_registered = True
        print("✅ 한글 폰트 등록 완료")
        return True
    except Exception as e:
        print(f"Font registration error: {e}")
        return False


def get_logo_image():
    """S3에서 로고 이미지 가져오기 (캐싱)"""
    global _logo_bytes

    if _logo_bytes:
        return io.BytesIO(_logo_bytes)

    try:
        import boto3
        from botocore.exceptions import ClientError

        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'

        if use_s3:
            # S3에서 로고 가져오기
            s3_bucket = os.getenv('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
            s3 = boto3.client('s3')

            try:
                response = s3.get_object(Bucket=s3_bucket, Key='assets/StockPlay.png')
                _logo_bytes = response['Body'].read()
                print("✅ S3에서 로고 로드 완료")
                return io.BytesIO(_logo_bytes)
            except ClientError as e:
                print(f"S3 로고 로드 실패: {e}")
                return None
        else:
            # 로컬에서 로고 가져오기 (개발 환경)
            logo_path = os.path.join(os.path.dirname(__file__), '../../assets/StockPlay.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    _logo_bytes = f.read()
                print("✅ 로컬에서 로고 로드 완료")
                return io.BytesIO(_logo_bytes)
            else:
                print("⚠️ 로고 파일을 찾을 수 없습니다")
                return None

    except Exception as e:
        print(f"로고 로드 오류: {e}")
        return None


def generate_dashboard_pdf(signal_data: Dict[str, Any]) -> bytes:
    """
    Dashboard용 간단 PDF 생성 (차트는 프론트엔드에서)
    
    Args:
        signal_data: 시그널 데이터
        
    Returns:
        PDF 바이트 데이터
    """
    register_korean_fonts()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # 커스텀 스타일
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#4c6fff'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='NanumGothic-Bold',
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a1f3a'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='NanumGothic-Bold',
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1a1f3a'),
        fontName='NanumGothic',
    )

    # 0. 로고 (상단 중앙)
    logo_image_data = get_logo_image()
    if logo_image_data:
        try:
            logo = Image(logo_image_data, width=1.5*inch, height=1.5*inch)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 0.2*inch))
        except Exception as e:
            print(f"로고 추가 실패: {e}")

    # 1. 제목
    title = Paragraph(f"<b>StockPlay 시그널 카드</b>", title_style)
    story.append(title)
    
    date_text = Paragraph(f"생성: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", normal_style)
    story.append(date_text)
    story.append(Spacer(1, 0.3*inch))
    
    # 2. 종목 정보
    story.append(Paragraph("📈 종목 정보", heading_style))
    
    signal_type_kr = {
        'BUY': '매수 🟢',
        'HOLD': '홀드 🟡',
        'SELL': '매도 🔴'
    }.get(signal_data.get('signalType', 'BUY'), '매수')
    
    info_data = [
        ['종목', f"{signal_data.get('companyName', 'N/A')} ({signal_data.get('symbol', 'N/A')})"],
        ['업종', signal_data.get('sector', 'N/A')],
        ['시그널', signal_type_kr],
        ['예측 기간', signal_data.get('period', '1d')],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1f3a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'NanumGothic-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'NanumGothic'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 0.3*inch))
    
    # 3. 핵심 지표
    story.append(Paragraph("💰 핵심 지표", heading_style))
    
    metrics_data = [
        ['지표', '값'],
        ['예상 수익률', f"{signal_data.get('expectedReturn', 0):+.1f}%"],
        ['KOSPI 대비', f"{signal_data.get('vsKospi', 0):+.1f}%"],
        ['KOSPI 수익률', f"{signal_data.get('kospiReturn', 0):+.1f}%"],
        ['신뢰도', f"{signal_data.get('confidenceScore', 0):.0f}%"],
        ['Surprise Z-Score', f"{signal_data.get('surpriseZ', 0):.2f}"],
        ['YoY 성장률', f"{signal_data.get('yoyGrowth', 0):.1f}%"],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(metrics_table)
    story.append(Spacer(1, 0.5*inch))
    
    # 4. 푸터
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='NanumGothic',
    )
    
    footer_text = """
    <br/>
    ⚠️ 본 리포트는 AI 분석 기반 참고 자료이며, 투자 판단 및 결과에 대한 책임은 투자자 본인에게 있습니다.<br/>
    <br/>
    Generated by StockPlay AI<br/>
    📊 자세한 차트는 웹사이트에서 확인하세요
    """
    
    story.append(Paragraph(footer_text, footer_style))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue()


def generate_full_report_pdf(signal_data: Dict[str, Any], ai_analysis: Optional[Dict[str, str]] = None) -> bytes:
    """
    Reports용 상세 PDF 생성 (AI 분석 포함)
    
    Args:
        signal_data: 시그널 데이터
        ai_analysis: AI 분석 결과 (optional)
        
    Returns:
        PDF 바이트 데이터
    """
    register_korean_fonts()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # 커스텀 스타일
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor('#4c6fff'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='NanumGothic-Bold',
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a1f3a'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='NanumGothic-Bold',
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1a1f3a'),
        fontName='NanumGothic',
        leading=14,
    )
    
    # 1. 제목
    title = Paragraph(f"<b>StockPlay 전문 투자 리포트</b>", title_style)
    story.append(title)
    
    subtitle = Paragraph(f"AI 기반 상세 분석 리포트", normal_style)
    story.append(subtitle)
    story.append(Spacer(1, 0.3*inch))
    
    # 2. 종목 개요
    story.append(Paragraph("📊 종목 개요", heading_style))
    
    signal_type_kr = {
        'BUY': '매수 (강력 추천)',
        'HOLD': '홀드 (관망)',
        'SELL': '매도 (주의)'
    }.get(signal_data.get('signalType', 'BUY'), '매수')
    
    company_name = signal_data.get('companyName', 'N/A')
    symbol = signal_data.get('symbol', 'N/A')

    overview_text = f"""
    <b>종목:</b> {company_name} ({symbol})<br/>
    <b>업종:</b> {signal_data.get('sector', 'N/A')}<br/>
    <b>투자의견:</b> {signal_type_kr}<br/>
    <b>예측기간:</b> {signal_data.get('period', '1d')}<br/>
    <br/>
    """

    if ai_analysis and 'overview' in ai_analysis:
        overview_text += ai_analysis['overview']
    else:
        overview_text += f"""
        {company_name}({symbol})은(는) {signal_data.get('sector')} 섹터의 종목으로,
        최근 Surprise 지표가 {signal_data.get('surpriseZ', 0):.2f}를 기록하며
        {'긍정적인' if signal_data.get('surpriseZ', 0) > 0 else '부정적인'} 신호를 보이고 있습니다.
        """
    
    story.append(Paragraph(overview_text, normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # 3. 투자 의견
    story.append(Paragraph("💡 투자 의견", heading_style))
    
    if ai_analysis and 'investment_opinion' in ai_analysis:
        opinion_text = ai_analysis['investment_opinion']
    else:
        expected = signal_data.get('expectedReturn', 0)
        vs_kospi = signal_data.get('vsKospi', 0)
        
        opinion_text = f"""
        <b>{signal_data.get('period', '1d')} 기준 예상 수익률:</b> {expected:+.1f}%<br/>
        <b>KOSPI 대비:</b> {vs_kospi:+.1f}%p<br/>
        <br/>
        본 종목은 {signal_data.get('period')} 기간 동안 {expected:+.1f}%의 수익률이 예상되며,
        이는 KOSPI 대비 {abs(vs_kospi):.1f}%p {'높은' if vs_kospi > 0 else '낮은'} 수준입니다.
        현재 시장 상황을 고려할 때 {'매수' if expected > 0 else '매도'} 포지션을 권장합니다.
        """
    
    story.append(Paragraph(opinion_text, normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # 4. 리스크 분석
    story.append(Paragraph("⚠️ 리스크 분석", heading_style))
    
    if ai_analysis and 'risk_analysis' in ai_analysis:
        risk_text = ai_analysis['risk_analysis']
    else:
        confidence = signal_data.get('confidenceScore', 0)
        risk_text = f"""
        <b>신뢰도:</b> {confidence:.0f}%<br/>
        <br/>
        주요 리스크 요인:<br/>
        • 시장 변동성에 따른 예측 오차 가능성<br/>
        • 예상 수익률은 과거 데이터 기반이며 미래 보장 불가<br/>
        • 거시경제 및 산업 트렌드 변화 리스크<br/>
        """
    
    story.append(Paragraph(risk_text, normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # 5. 기술적 지표
    story.append(Paragraph("📈 기술적 지표", heading_style))
    
    if ai_analysis and 'technical_analysis' in ai_analysis:
        tech_text = ai_analysis['technical_analysis']
        story.append(Paragraph(tech_text, normal_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    technical_data = [
        ['지표', '값', '의미'],
        ['Surprise Z-Score', f"{signal_data.get('surpriseZ', 0):.2f}", 
         '높을수록 긍정' if signal_data.get('surpriseZ', 0) > 0 else '낮을수록 부정'],
        ['YoY 성장률', f"{signal_data.get('yoyGrowth', 0):.1f}%", '전년 대비 성장'],
        ['예상 수익률', f"{signal_data.get('expectedReturn', 0):+.1f}%", '예측 수익'],
        ['KOSPI 대비', f"{signal_data.get('vsKospi', 0):+.1f}%", '지수 대비 성과'],
        ['신뢰도', f"{signal_data.get('confidenceScore', 0):.0f}%", '모델 신뢰도'],
    ]
    
    tech_table = Table(technical_data, colWidths=[2*inch, 1.8*inch, 2.2*inch])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(tech_table)
    story.append(Spacer(1, 0.4*inch))
    
    # 6. 푸터
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='NanumGothic',
    )
    
    footer_text = f"""
    <br/>
    <b>생성일:</b> {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}<br/>
    <br/>
    ⚠️ 본 리포트는 AI 분석 기반 참고 자료이며, 투자 판단 및 결과에 대한 책임은 투자자 본인에게 있습니다.<br/>
    StockPlay는 데이터 분석을 제공할 뿐, 투자 손실에 대한 책임을 지지 않습니다.<br/>
    <br/>
    Generated by StockPlay AI<br/>
    📊 자세한 차트는 웹사이트에서 확인하세요
    """
    
    story.append(Paragraph(footer_text, footer_style))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue()


# 기존 함수 유지 (하위 호환성)
def generate_report_pdf(report_data: Dict[str, Any]) -> bytes:
    """기존 월간 리포트 PDF 생성"""
    register_korean_fonts()
    
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    
    story = []
    styles = getSampleStyleSheet()
    
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
    
    date_str = datetime.fromisoformat(report_data['date']).strftime('%Y년 %m월')
    title = Paragraph(f"<b>StockPlay Monthly Report</b><br/>{date_str}", title_style)
    story.append(title)
    story.append(Spacer(1, 0.3 * inch))
    
    story.append(Paragraph("📈 백테스트 성과", heading_style))
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(perf_table)
    story.append(Spacer(1, 0.5 * inch))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='NanumGothic',
    )
    
    created_date = datetime.fromisoformat(report_data['createdAt']).strftime('%Y년 %m월 %d일')
    footer_text = f"""
    <br/><br/>
    생성일: {created_date}<br/>
    <br/>
    ⚠️ 본 리포트는 투자 참고 자료입니다.
    """
    
    story.append(Paragraph(footer_text, footer_style))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue()


def save_pdf_locally(pdf_bytes: bytes, filename: str) -> str:
    """로컬 파일로 PDF 저장"""
    filepath = f"data/reports/{filename}"
    
    import os
    os.makedirs("data/reports", exist_ok=True)
    
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)
    
    return filepath


def upload_to_s3(pdf_bytes: bytes, filename: str, bucket_name: str = 'stockplay-reports') -> str:
    """S3에 PDF 업로드"""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        s3 = boto3.client('s3')
        
        s3.put_object(
            Bucket=bucket_name,
            Key=f"reports/{filename}",
            Body=pdf_bytes,
            ContentType='application/pdf',
            ContentDisposition=f'attachment; filename="{filename}"'
        )
        
        url = f"https://{bucket_name}.s3.amazonaws.com/reports/{filename}"
        
        return url
        
    except ClientError as e:
        print(f"S3 upload error: {e}")
        raise


def get_s3_presigned_url(bucket_name: str, key: str, expiration: int = 3600) -> str:
    """S3 파일에 대한 presigned URL 생성

    Args:
        bucket_name: S3 버킷 이름
        key: S3 객체 키
        expiration: URL 만료 시간(초, 기본 1시간)

    Returns:
        presigned URL
    """
    import boto3
    from botocore.exceptions import ClientError

    try:
        s3 = boto3.client('s3')

        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': key
            },
            ExpiresIn=expiration
        )

        return url

    except ClientError as e:
        print(f"Presigned URL generation error: {e}")
        raise