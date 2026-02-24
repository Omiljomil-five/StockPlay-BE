"""PDF report generator using Jinja2 + WeasyPrint.

Replaces the previous ReportLab implementation.
Public API is unchanged: generate_full_report_pdf, generate_dashboard_pdf,
generate_report_pdf, upload_to_s3, save_pdf_locally, get_s3_presigned_url.
"""

from datetime import datetime
from pathlib import Path
import base64
import io
import os
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration


# ─── Paths ────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_DIR = _PROJECT_ROOT / 'templates'
_FONT_DIR = _PROJECT_ROOT / 'fonts'

# ─── Jinja2 Environment (singleton) ──────────────────────
_jinja_env: Optional[Environment] = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=False,
        )
    return _jinja_env


# ─── Core render helper ──────────────────────────────────
def _render_pdf(template_name: str, context: dict) -> bytes:
    """Render *template_name* with *context* → PDF bytes."""
    env = _get_jinja_env()
    template = env.get_template(template_name)
    html_str = template.render(**context)

    font_config = FontConfiguration()
    pdf_bytes = HTML(string=html_str).write_pdf(font_config=font_config)
    return pdf_bytes


# ─── Chart helpers ────────────────────────────────────────
def _chart_to_b64(chart_bytes: bytes) -> str:
    """PNG bytes → base64 string for <img src="data:...">."""
    return base64.b64encode(chart_bytes).decode('ascii')


def _generate_chart_safe(primary_fn, fallback_fn, *args, **kwargs) -> Optional[str]:
    """Try *primary_fn*, fall back to *fallback_fn*, return base64 or None."""
    try:
        return _chart_to_b64(primary_fn(*args, **kwargs))
    except Exception as e:
        print(f"Chart primary failed ({primary_fn.__name__}): {e}")
    if fallback_fn:
        try:
            return _chart_to_b64(fallback_fn(*args, **kwargs))
        except Exception as e2:
            print(f"Chart fallback failed ({fallback_fn.__name__}): {e2}")
    return None


# ─── Signal helpers ───────────────────────────────────────
_SIGNAL_LABELS = {'BUY': 'BUY (매수)', 'HOLD': 'HOLD (관망)', 'SELL': 'SELL (매도)'}
_SIGNAL_COLORS = {'BUY': 'buy', 'HOLD': 'hold', 'SELL': 'sell'}


def _css_class_for_value(value: float, positive_threshold: float = 0) -> str:
    return 'buy' if value >= positive_threshold else 'sell'


def _css_class_for_confidence(score: float) -> str:
    if score >= 70:
        return 'buy'
    return 'hold' if score >= 40 else 'sell'


# ─── Logo helper ──────────────────────────────────────────
_logo_bytes: Optional[bytes] = None


def _get_logo_b64() -> Optional[str]:
    global _logo_bytes
    if _logo_bytes:
        return base64.b64encode(_logo_bytes).decode('ascii')
    try:
        import boto3
        from botocore.exceptions import ClientError
        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        if use_s3:
            s3_bucket = os.getenv('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
            s3 = boto3.client('s3')
            try:
                resp = s3.get_object(Bucket=s3_bucket, Key='assets/StockPlay.png')
                _logo_bytes = resp['Body'].read()
                return base64.b64encode(_logo_bytes).decode('ascii')
            except ClientError:
                pass
        else:
            logo_path = _PROJECT_ROOT / 'assets' / 'StockPlay.png'
            if logo_path.exists():
                _logo_bytes = logo_path.read_bytes()
                return base64.b64encode(_logo_bytes).decode('ascii')
    except Exception:
        pass
    return None


# ─── Build full-report context ────────────────────────────
def _build_full_context(signal_data: Dict[str, Any],
                        ai_analysis: Optional[Dict[str, str]] = None) -> dict:
    company_name = signal_data.get('companyName', 'N/A')
    symbol = signal_data.get('symbol', 'N/A')
    sector = signal_data.get('sector', 'N/A')
    signal_type = signal_data.get('signalType', 'BUY')
    period = signal_data.get('period', '1d')
    date_str = datetime.now().strftime('%Y.%m.%d')

    expected_return = signal_data.get('expectedReturn', 0)
    vs_kospi = signal_data.get('vsKospi', 0)
    confidence = signal_data.get('confidenceScore', 0)
    surprise_z = signal_data.get('surpriseZ', 0)
    yoy_growth = signal_data.get('yoyGrowth', 0)
    kospi_return = signal_data.get('kospiReturn', 0)

    # ── Charts (matplotlib primary, pillow fallback) ──────
    kospi_chart_b64 = None
    surprise_chart_b64 = None
    comparison_chart_b64 = None
    gauge_chart_b64 = None

    try:
        from .chart_generator import generate_kospi_advanced_chart
        primary_kospi = generate_kospi_advanced_chart
    except ImportError:
        primary_kospi = None
    try:
        from .chart_generator_pillow import generate_kospi_chart_pillow
        fallback_kospi = generate_kospi_chart_pillow
    except ImportError:
        fallback_kospi = None
    if primary_kospi:
        kospi_chart_b64 = _generate_chart_safe(primary_kospi, fallback_kospi, signal_data, days=60)
    elif fallback_kospi:
        kospi_chart_b64 = _generate_chart_safe(fallback_kospi, None, signal_data, days=60)

    try:
        from .chart_generator import generate_surprise_chart
        primary_surprise = generate_surprise_chart
    except ImportError:
        primary_surprise = None
    try:
        from .chart_generator_pillow import generate_surprise_chart_pillow
        fallback_surprise = generate_surprise_chart_pillow
    except ImportError:
        fallback_surprise = None
    if primary_surprise:
        surprise_chart_b64 = _generate_chart_safe(primary_surprise, fallback_surprise, signal_data, history_days=30)
    elif fallback_surprise:
        surprise_chart_b64 = _generate_chart_safe(fallback_surprise, None, signal_data, history_days=30)

    try:
        from .chart_generator import generate_kospi_comparison_chart
        primary_comp = generate_kospi_comparison_chart
    except ImportError:
        primary_comp = None
    try:
        from .chart_generator_pillow import generate_comparison_chart_pillow
        fallback_comp = generate_comparison_chart_pillow
    except ImportError:
        fallback_comp = None
    if primary_comp:
        comparison_chart_b64 = _generate_chart_safe(primary_comp, fallback_comp, signal_data)
    elif fallback_comp:
        comparison_chart_b64 = _generate_chart_safe(fallback_comp, None, signal_data)

    try:
        from .chart_generator import generate_confidence_gauge
        primary_gauge = generate_confidence_gauge
    except ImportError:
        primary_gauge = None
    try:
        from .chart_generator_pillow import generate_confidence_gauge_pillow
        fallback_gauge = generate_confidence_gauge_pillow
    except ImportError:
        fallback_gauge = None
    if primary_gauge:
        gauge_chart_b64 = _generate_chart_safe(primary_gauge, fallback_gauge, confidence)
    elif fallback_gauge:
        gauge_chart_b64 = _generate_chart_safe(fallback_gauge, None, confidence)

    # ── AI Analysis texts ─────────────────────────────────
    if ai_analysis and 'overview' in ai_analysis:
        overview_text = ai_analysis['overview']
    else:
        trend = 'positive' if surprise_z > 0 else 'negative'
        overview_text = (
            f"{company_name}({symbol}) is in the {sector} sector. "
            f"Recent Surprise indicator recorded {surprise_z:.2f}, "
            f"showing a {trend} signal based on export data analysis."
        )

    if ai_analysis and 'investment_opinion' in ai_analysis:
        opinion_text = ai_analysis['investment_opinion']
    else:
        direction = 'outperforms' if vs_kospi > 0 else 'underperforms'
        opinion_text = (
            f"Expected return ({period}): {expected_return:+.1f}% | "
            f"vs KOSPI: {vs_kospi:+.1f}%p. "
            f"This equity {direction} the KOSPI benchmark by {abs(vs_kospi):.1f}%p."
        )

    if ai_analysis and 'risk_analysis' in ai_analysis:
        risk_text = ai_analysis['risk_analysis']
    else:
        risk_text = (
            f"Model Confidence: {confidence:.0f}%. "
            "Key risks: Market volatility may affect prediction accuracy. "
            "Expected returns are based on historical data and do not guarantee future results. "
            "Macroeconomic and sector trend changes may impact performance."
        )

    # ── Tech indicators table rows ────────────────────────
    tech_indicators = [
        {'indicator': 'Surprise Z-Score', 'value': f'{surprise_z:.2f}',
         'interpretation': 'Positive signal' if surprise_z > 0 else 'Negative signal'},
        {'indicator': 'YoY Growth', 'value': f'{yoy_growth:.1f}%',
         'interpretation': 'Year-over-Year growth rate'},
        {'indicator': 'Expected Return', 'value': f'{expected_return:+.1f}%',
         'interpretation': 'Predicted return'},
        {'indicator': 'vs KOSPI', 'value': f'{vs_kospi:+.1f}%p',
         'interpretation': 'Relative to market'},
        {'indicator': 'KOSPI Return', 'value': f'{kospi_return:+.1f}%',
         'interpretation': 'Market benchmark'},
        {'indicator': 'Confidence', 'value': f'{confidence:.0f}%',
         'interpretation': 'Model confidence level'},
    ]

    return {
        'company_name': company_name,
        'symbol': symbol,
        'sector': sector,
        'date_str': date_str,
        'period': period,
        'signal_label': _SIGNAL_LABELS.get(signal_type, signal_type),
        'signal_color': _SIGNAL_COLORS.get(signal_type, 'buy'),
        # Metric cards
        'expected_return': f'{expected_return:+.1f}%',
        'vs_kospi': f'{vs_kospi:+.1f}%p',
        'confidence': f'{confidence:.0f}%',
        'ret_class': _css_class_for_value(expected_return),
        'vs_class': _css_class_for_value(vs_kospi),
        'conf_class': _css_class_for_confidence(confidence),
        # Secondary metrics
        'surprise_z': f'{surprise_z:.2f}',
        'yoy_growth': f'{yoy_growth:.1f}%',
        'kospi_return': f'{kospi_return:+.1f}%',
        # Charts (base64)
        'kospi_chart_b64': kospi_chart_b64,
        'surprise_chart_b64': surprise_chart_b64,
        'comparison_chart_b64': comparison_chart_b64,
        'gauge_chart_b64': gauge_chart_b64,
        # Analysis texts
        'overview_text': overview_text,
        'opinion_text': opinion_text,
        'risk_text': risk_text,
        # Table + timestamps
        'tech_indicators': tech_indicators,
        'generated_at': datetime.now().strftime('%Y.%m.%d %H:%M'),
        'generated_at_full': datetime.now().strftime('%Y-%m-%d %H:%M:%S KST'),
    }


# ═══════════════════════════════════════════════════════════
#  Public API (signatures unchanged)
# ═══════════════════════════════════════════════════════════

def generate_full_report_pdf(signal_data: Dict[str, Any],
                             ai_analysis: Optional[Dict[str, str]] = None) -> bytes:
    """Generate premium multi-page PDF report.

    Page 1: Cover + Executive Summary
    Page 2: Technical Analysis (KOSPI, Surprise, Comparison)
    Page 3: AI Analysis + Risk + Technical Indicators + Disclaimer
    """
    ctx = _build_full_context(signal_data, ai_analysis)
    return _render_pdf('report_full.html', ctx)


def generate_dashboard_pdf(signal_data: Dict[str, Any]) -> bytes:
    """Dashboard simple PDF (backward-compatible)."""
    now = datetime.now()
    ctx = {
        'company_name': signal_data.get('companyName', 'N/A'),
        'symbol': signal_data.get('symbol', 'N/A'),
        'sector': signal_data.get('sector', 'N/A'),
        'signal_type': signal_data.get('signalType', 'BUY'),
        'period': signal_data.get('period', '1d'),
        'expected_return': f"{signal_data.get('expectedReturn', 0):+.1f}%",
        'vs_kospi': f"{signal_data.get('vsKospi', 0):+.1f}%",
        'kospi_return': f"{signal_data.get('kospiReturn', 0):+.1f}%",
        'confidence': f"{signal_data.get('confidenceScore', 0):.0f}%",
        'surprise_z': f"{signal_data.get('surpriseZ', 0):.2f}",
        'yoy_growth': f"{signal_data.get('yoyGrowth', 0):.1f}%",
        'generated_at': now.strftime('%Y.%m.%d %H:%M'),
        'logo_b64': _get_logo_b64(),
    }
    return _render_pdf('report_dashboard.html', ctx)


def generate_report_pdf(report_data: Dict[str, Any]) -> bytes:
    """Monthly report PDF (backward-compatible)."""
    performance = report_data['analysisResult']['performance']
    date_str = datetime.fromisoformat(report_data['date']).strftime('%Y.%m')
    created_date = datetime.fromisoformat(report_data['createdAt']).strftime('%Y.%m.%d')

    ctx = {
        'date_str': date_str,
        'avg_return': performance['avgReturn'],
        'win_rate': performance['winRate'],
        'sharpe_ratio': performance['sharpeRatio'],
        'max_drawdown': performance['maxDrawdown'],
        'created_date': created_date,
    }
    return _render_pdf('report_monthly.html', ctx)


# ═══════════════════════════════════════════════════════════
#  Utility Functions (unchanged)
# ═══════════════════════════════════════════════════════════

def save_pdf_locally(pdf_bytes: bytes, filename: str) -> str:
    """Save PDF to local file."""
    filepath = f"data/reports/{filename}"
    os.makedirs("data/reports", exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)
    return filepath


def upload_to_s3(pdf_bytes: bytes, filename: str,
                 bucket_name: str = 'stockplay-reports-yjw-20251113') -> str:
    """Upload PDF to S3."""
    import boto3
    from botocore.exceptions import ClientError

    try:
        s3 = boto3.client('s3', region_name='ap-northeast-2')
        s3.put_object(
            Bucket=bucket_name,
            Key=f"reports/{filename}",
            Body=pdf_bytes,
            ContentType='application/pdf',
            ContentDisposition=f'attachment; filename="{filename}"'
        )
        return f"https://{bucket_name}.s3.amazonaws.com/reports/{filename}"
    except ClientError as e:
        print(f"S3 upload error: {e}")
        raise


def get_s3_presigned_url(bucket_name: str, key: str, expiration: int = 3600) -> str:
    """Generate S3 presigned URL."""
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    try:
        s3 = boto3.client(
            's3',
            region_name='ap-northeast-2',
            config=Config(signature_version='s3v4')
        )
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"Presigned URL generation error: {e}")
        raise
