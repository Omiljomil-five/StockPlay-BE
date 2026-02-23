from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import io
import os
from typing import Dict, Any, Optional, List


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


def _build_premium_styles(styles):
    """프리미엄 리포트용 스타일 모음"""
    return {
        'title': ParagraphStyle(
            'PremiumTitle', parent=styles['Title'],
            fontSize=26, textColor=colors.HexColor('#ffffff'),
            spaceAfter=10, alignment=TA_CENTER,
            fontName='NanumGothic-Bold',
        ),
        'subtitle': ParagraphStyle(
            'PremiumSubtitle', parent=styles['Normal'],
            fontSize=12, textColor=colors.HexColor('#b0b8ff'),
            alignment=TA_CENTER, fontName='NanumGothic',
        ),
        'heading': ParagraphStyle(
            'PremiumHeading', parent=styles['Heading2'],
            fontSize=15, textColor=colors.HexColor('#4c6fff'),
            spaceAfter=10, spaceBefore=15,
            fontName='NanumGothic-Bold',
        ),
        'subheading': ParagraphStyle(
            'PremiumSubheading', parent=styles['Heading3'],
            fontSize=12, textColor=colors.HexColor('#1a1f3a'),
            spaceAfter=8, spaceBefore=10,
            fontName='NanumGothic-Bold',
        ),
        'normal': ParagraphStyle(
            'PremiumNormal', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#1a1f3a'),
            fontName='NanumGothic', leading=15,
        ),
        'small': ParagraphStyle(
            'PremiumSmall', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#666666'),
            fontName='NanumGothic', leading=11,
        ),
        'footer': ParagraphStyle(
            'PremiumFooter', parent=styles['Normal'],
            fontSize=8, textColor=colors.grey,
            alignment=TA_CENTER, fontName='NanumGothic',
        ),
        'metric_value': ParagraphStyle(
            'MetricValue', parent=styles['Normal'],
            fontSize=20, textColor=colors.HexColor('#4c6fff'),
            alignment=TA_CENTER, fontName='NanumGothic-Bold',
        ),
        'metric_label': ParagraphStyle(
            'MetricLabel', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER, fontName='NanumGothic',
        ),
    }


def _build_page1_cover(story, signal_data, ps):
    """Page 1: Cover + Summary"""

    # 그라디언트 헤더 (테이블 배경으로 시뮬레이션)
    header_data = [['']]
    header_table = Table(header_data, colWidths=[6.5*inch], rowHeights=[1.8*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#4c6fff')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)

    # 로고 + 타이틀 (헤더 위에 겹치기는 어려우므로 별도 배치)
    logo_image_data = get_logo_image()
    if logo_image_data:
        try:
            logo = Image(logo_image_data, width=1.2*inch, height=1.2*inch)
            logo.hAlign = 'CENTER'
            story.append(Spacer(1, -1.6*inch))
            story.append(logo)
        except Exception:
            pass

    story.append(Paragraph("<b>StockPlay Premium Report</b>", ps['title']))
    story.append(Paragraph("AI-Powered Investment Analysis", ps['subtitle']))
    story.append(Spacer(1, 0.4*inch))

    # 날짜 + 기간 정보
    company_name = signal_data.get('companyName', 'N/A')
    symbol = signal_data.get('symbol', 'N/A')
    signal_type = signal_data.get('signalType', 'BUY')
    period = signal_data.get('period', '1d')

    # 종목 정보 바
    info_text = f"""
    <b>{company_name}</b> ({symbol}) | {signal_data.get('sector', 'N/A')} |
    {datetime.now().strftime('%Y.%m.%d')} | {period}
    """
    story.append(Paragraph(info_text, ParagraphStyle(
        'InfoBar', parent=ps['normal'], alignment=TA_CENTER,
        fontSize=11, textColor=colors.HexColor('#333333'),
        fontName='NanumGothic',
    )))
    story.append(Spacer(1, 0.1*inch))

    # 시그널 배지
    signal_colors = {'BUY': '#10b981', 'HOLD': '#f59e0b', 'SELL': '#ef4444'}
    signal_labels = {'BUY': 'BUY (매수)', 'HOLD': 'HOLD (관망)', 'SELL': 'SELL (매도)'}
    badge_color = colors.HexColor(signal_colors.get(signal_type, '#4c6fff'))

    badge_data = [[signal_labels.get(signal_type, signal_type)]]
    badge_table = Table(badge_data, colWidths=[2.5*inch], rowHeights=[0.4*inch])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), badge_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'NanumGothic-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    badge_table.hAlign = 'CENTER'
    story.append(badge_table)
    story.append(Spacer(1, 0.4*inch))

    # 핵심 지표 카드 3개
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
    story.append(Spacer(1, 0.2*inch))

    expected_return = signal_data.get('expectedReturn', 0)
    vs_kospi = signal_data.get('vsKospi', 0)
    confidence = signal_data.get('confidenceScore', 0)

    ret_color = '#10b981' if expected_return >= 0 else '#ef4444'
    vs_color = '#10b981' if vs_kospi >= 0 else '#ef4444'
    conf_color = '#10b981' if confidence >= 70 else ('#f59e0b' if confidence >= 40 else '#ef4444')

    metric_data = [
        [
            Paragraph(f'<font color="{ret_color}"><b>{expected_return:+.1f}%</b></font>', ps['metric_value']),
            Paragraph(f'<font color="{vs_color}"><b>{vs_kospi:+.1f}%p</b></font>', ps['metric_value']),
            Paragraph(f'<font color="{conf_color}"><b>{confidence:.0f}%</b></font>', ps['metric_value']),
        ],
        [
            Paragraph('Expected Return', ps['metric_label']),
            Paragraph('vs KOSPI', ps['metric_label']),
            Paragraph('Confidence', ps['metric_label']),
        ]
    ]

    metric_table = Table(metric_data, colWidths=[2.17*inch, 2.17*inch, 2.17*inch])
    metric_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 15),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 15),
        ('LINEAFTER', (0, 0), (1, -1), 1, colors.HexColor('#e0e0e0')),
    ]))
    story.append(metric_table)

    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
    story.append(Spacer(1, 0.3*inch))

    # 추가 지표
    extra_data = [
        ['Surprise Z-Score', 'YoY Growth', 'KOSPI Return'],
        [f"{signal_data.get('surpriseZ', 0):.2f}",
         f"{signal_data.get('yoyGrowth', 0):.1f}%",
         f"{signal_data.get('kospiReturn', 0):+.1f}%"],
    ]

    extra_table = Table(extra_data, colWidths=[2.17*inch, 2.17*inch, 2.17*inch])
    extra_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f4ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#1a1f3a')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),
        ('FONTNAME', (0, 1), (-1, 1), 'NanumGothic'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, 1), 13),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e0e0e0')),
    ]))
    story.append(extra_table)


def _build_page2_technical(story, signal_data, ps):
    """Page 2: Technical Analysis Charts"""
    story.append(PageBreak())

    story.append(Paragraph("Technical Analysis", ps['heading']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#4c6fff')))
    story.append(Spacer(1, 0.2*inch))

    # 1. KOSPI Advanced Chart
    story.append(Paragraph("KOSPI Market Analysis", ps['subheading']))
    try:
        from .chart_generator import generate_kospi_advanced_chart
        kospi_chart_bytes = generate_kospi_advanced_chart(signal_data, days=60)
        kospi_img = Image(io.BytesIO(kospi_chart_bytes), width=6.5*inch, height=3.5*inch)
        kospi_img.hAlign = 'CENTER'
        story.append(kospi_img)
    except Exception as e:
        print(f"⚠️ KOSPI advanced chart failed: {e}")
        try:
            from .chart_generator_pillow import generate_kospi_chart_pillow
            fallback = generate_kospi_chart_pillow(signal_data, days=60)
            fb_img = Image(io.BytesIO(fallback), width=6.5*inch, height=3.25*inch)
            fb_img.hAlign = 'CENTER'
            story.append(fb_img)
        except Exception as e2:
            print(f"⚠️ Pillow chart fallback also failed: {e2}")
            story.append(Paragraph("KOSPI chart unavailable", ps['small']))

    story.append(Spacer(1, 0.25*inch))

    # 2. Surprise Z-Score + KOSPI Comparison (나란히는 어려우므로 순서대로)
    story.append(Paragraph("Surprise Z-Score Timeline", ps['subheading']))
    try:
        from .chart_generator import generate_surprise_chart
        surprise_bytes = generate_surprise_chart(signal_data, history_days=30)
        surprise_img = Image(io.BytesIO(surprise_bytes), width=6.5*inch, height=3*inch)
        surprise_img.hAlign = 'CENTER'
        story.append(surprise_img)
    except Exception as e:
        print(f"⚠️ Surprise chart failed: {e}")
        story.append(Paragraph("Surprise Z-Score chart unavailable", ps['small']))

    story.append(Spacer(1, 0.25*inch))

    story.append(Paragraph("Performance vs KOSPI", ps['subheading']))
    try:
        from .chart_generator import generate_kospi_comparison_chart
        comparison_bytes = generate_kospi_comparison_chart(signal_data)
        comp_img = Image(io.BytesIO(comparison_bytes), width=6.5*inch, height=3*inch)
        comp_img.hAlign = 'CENTER'
        story.append(comp_img)
    except Exception as e:
        print(f"⚠️ Comparison chart failed: {e}")
        story.append(Paragraph("Comparison chart unavailable", ps['small']))


def _build_page3_analysis(story, signal_data, ai_analysis, ps):
    """Page 3: AI Analysis + Risk + Technical Table"""
    story.append(PageBreak())

    story.append(Paragraph("AI Analysis & Risk Assessment", ps['heading']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#4c6fff')))
    story.append(Spacer(1, 0.2*inch))

    company_name = signal_data.get('companyName', 'N/A')
    symbol = signal_data.get('symbol', 'N/A')

    # 1. AI 투자 의견
    story.append(Paragraph("AI Investment Opinion", ps['subheading']))

    if ai_analysis and 'overview' in ai_analysis:
        story.append(Paragraph(ai_analysis['overview'], ps['normal']))
    else:
        overview = f"""
        {company_name}({symbol})은(는) {signal_data.get('sector')} 섹터의 종목으로,
        최근 Surprise 지표가 {signal_data.get('surpriseZ', 0):.2f}를 기록하며
        {'긍정적인' if signal_data.get('surpriseZ', 0) > 0 else '부정적인'} 신호를 보이고 있습니다.
        """
        story.append(Paragraph(overview, ps['normal']))

    story.append(Spacer(1, 0.1*inch))

    if ai_analysis and 'investment_opinion' in ai_analysis:
        story.append(Paragraph(ai_analysis['investment_opinion'], ps['normal']))
    else:
        expected = signal_data.get('expectedReturn', 0)
        vs_kospi = signal_data.get('vsKospi', 0)
        opinion = f"""
        <b>{signal_data.get('period', '1d')} 기준 예상 수익률:</b> {expected:+.1f}%<br/>
        <b>KOSPI 대비:</b> {vs_kospi:+.1f}%p<br/>
        본 종목은 KOSPI 대비 {abs(vs_kospi):.1f}%p {'높은' if vs_kospi > 0 else '낮은'} 수준입니다.
        """
        story.append(Paragraph(opinion, ps['normal']))

    story.append(Spacer(1, 0.25*inch))

    # 2. 리스크 분석
    story.append(Paragraph("Risk Analysis", ps['subheading']))

    if ai_analysis and 'risk_analysis' in ai_analysis:
        story.append(Paragraph(ai_analysis['risk_analysis'], ps['normal']))
    else:
        confidence = signal_data.get('confidenceScore', 0)
        risk = f"""
        <b>Model Confidence:</b> {confidence:.0f}%<br/><br/>
        Risk Factors:<br/>
        - Market volatility may affect prediction accuracy<br/>
        - Expected returns are based on historical data and do not guarantee future results<br/>
        - Macroeconomic and sector trend changes may impact performance<br/>
        - Surprise Z-Score patterns may shift in unusual market conditions<br/>
        """
        story.append(Paragraph(risk, ps['normal']))

    story.append(Spacer(1, 0.25*inch))

    # 3. Confidence Gauge
    try:
        from .chart_generator import generate_confidence_gauge
        gauge_bytes = generate_confidence_gauge(signal_data.get('confidenceScore', 0))
        gauge_img = Image(io.BytesIO(gauge_bytes), width=3*inch, height=2*inch)
        gauge_img.hAlign = 'CENTER'
        story.append(gauge_img)
        story.append(Spacer(1, 0.2*inch))
    except Exception as e:
        print(f"⚠️ Confidence gauge failed: {e}")

    # 4. 기술적 지표 테이블
    story.append(Paragraph("Technical Indicators", ps['subheading']))

    technical_data = [
        ['Indicator', 'Value', 'Interpretation'],
        ['Surprise Z-Score', f"{signal_data.get('surpriseZ', 0):.2f}",
         'Positive signal' if signal_data.get('surpriseZ', 0) > 0 else 'Negative signal'],
        ['YoY Growth', f"{signal_data.get('yoyGrowth', 0):.1f}%", 'Year-over-Year growth rate'],
        ['Expected Return', f"{signal_data.get('expectedReturn', 0):+.1f}%", 'Predicted return'],
        ['vs KOSPI', f"{signal_data.get('vsKospi', 0):+.1f}%p", 'Relative to market index'],
        ['KOSPI Return', f"{signal_data.get('kospiReturn', 0):+.1f}%", 'Market benchmark'],
        ['Confidence', f"{signal_data.get('confidenceScore', 0):.0f}%", 'Model confidence level'],
    ]

    tech_table = Table(technical_data, colWidths=[2*inch, 1.5*inch, 3*inch])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4c6fff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'NanumGothic-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1f3a')),
        ('FONTNAME', (0, 1), (-1, -1), 'NanumGothic'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d0d0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8f9ff'), colors.HexColor('#ffffff')]),
    ]))

    story.append(tech_table)
    story.append(Spacer(1, 0.4*inch))

    # 5. 면책 조항
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
    story.append(Spacer(1, 0.1*inch))

    disclaimer = f"""
    <b>Disclaimer</b><br/>
    This report is generated by StockPlay AI for reference purposes only.
    Investment decisions and their outcomes are the sole responsibility of the investor.
    Past performance does not guarantee future results.
    StockPlay provides data analysis and does not bear responsibility for investment losses.<br/>
    <br/>
    <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}<br/>
    © 2025 StockPlay. All rights reserved.
    """
    story.append(Paragraph(disclaimer, ps['footer']))


def generate_full_report_pdf(signal_data: Dict[str, Any], ai_analysis: Optional[Dict[str, str]] = None) -> bytes:
    """
    프리미엄 멀티페이지 PDF 생성

    Page 1: Cover + Summary (핵심 지표 카드, 시그널 배지)
    Page 2: Technical Analysis (KOSPI Advanced, Surprise Z-Score, Comparison)
    Page 3: AI Analysis + Risk + Technical Table + Disclaimer

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
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()
    ps = _build_premium_styles(styles)

    story = []

    # Page 1: Cover + Summary
    _build_page1_cover(story, signal_data, ps)

    # Page 2: Technical Analysis Charts
    _build_page2_technical(story, signal_data, ps)

    # Page 3: AI Analysis + Risk
    _build_page3_analysis(story, signal_data, ai_analysis, ps)

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