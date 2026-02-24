"""Pillow lightweight chart generator (white professional theme)"""
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import io
import math
import random
from typing import List, Dict, Any, Tuple
import os
import csv
from io import StringIO

# ─── White Professional Theme Colors ──────────────────────────
BG_WHITE     = (255, 255, 255)
LINE_NAVY    = (27, 42, 74)      # PRIMARY_NAVY
SLATE        = (61, 90, 128)     # SECONDARY_SLATE
GRID_LIGHT   = (229, 232, 235)   # GRID_COLOR
TEXT_DARK    = (44, 62, 80)      # TEXT_DARK
TEXT_MEDIUM  = (93, 109, 126)    # TEXT_MEDIUM
TEXT_LIGHT   = (149, 165, 166)   # TEXT_LIGHT
ACCENT_GOLD  = (201, 169, 110)   # ACCENT_GOLD
BG_CARD      = (248, 249, 250)   # BG_CARD
SIGNAL_BUY   = (14, 124, 71)    # SIGNAL_BUY
SIGNAL_HOLD  = (212, 160, 23)   # SIGNAL_HOLD
SIGNAL_SELL  = (192, 57, 43)    # SIGNAL_SELL
EXCELLENT_GN = (10, 107, 61)


# ─── Font Loader ──────────────────────────────────────────────
def _load_fonts(scale=1):
    """Load fonts with optional scale factor"""
    font_path = os.path.join(os.path.dirname(__file__), '../../fonts')
    sizes = {
        'title': int(22 * scale),
        'value': int(16 * scale),
        'label': int(13 * scale),
        'small': int(11 * scale),
        'score': int(40 * scale),
    }
    fonts = {}
    for key, size in sizes.items():
        for path in [
            os.path.join(font_path, 'NanumGothic-Bold.ttf' if key in ('title', 'value', 'score') else 'NanumGothic-Regular.ttf'),
            "/System/Library/Fonts/Helvetica.ttc",
        ]:
            try:
                fonts[key] = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
        if key not in fonts:
            fonts[key] = ImageFont.load_default()
    return fonts


def _draw_dashed_line(draw, start, end, fill, width=1, dash_len=8, gap_len=5):
    """Draw a dashed line"""
    x0, y0 = start
    x1, y1 = end
    total_len = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
    if total_len == 0:
        return
    dx = (x1 - x0) / total_len
    dy = (y1 - y0) / total_len
    pos = 0
    while pos < total_len:
        seg_end = min(pos + dash_len, total_len)
        draw.line([
            (x0 + dx * pos, y0 + dy * pos),
            (x0 + dx * seg_end, y0 + dy * seg_end)
        ], fill=fill, width=width)
        pos += dash_len + gap_len


# ─── KOSPI Data Loader ────────────────────────────────────────
def load_kospi_data(days: int = 60) -> Tuple[List[datetime], List[float]]:
    """KOSPI data loader"""
    try:
        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        if use_s3:
            import boto3
            s3_bucket = os.getenv('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
            s3 = boto3.client('s3')
            obj = s3.get_object(Bucket=s3_bucket, Key='data/kospi.csv')
            csv_content = obj['Body'].read().decode('utf-8-sig')
            reader = csv.DictReader(StringIO(csv_content))
            data = [{'date': r.get('date', '').strip(), 'close': float(r.get('close', 0))} for r in reader]
        else:
            from pathlib import Path
            data_path = Path(__file__).parent.parent.parent / 'data' / 'kospi.csv'
            with open(data_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = [{'date': r.get('date', '').strip(), 'close': float(r.get('close', 0))} for r in reader]

        valid_data = sorted(
            [d for d in data if d.get('date') and d.get('close', 0) > 0],
            key=lambda x: x['date']
        )[-days:]

        if not valid_data:
            raise Exception("No valid KOSPI data")

        dates, closes = [], []
        for d in valid_data:
            try:
                dates.append(datetime.strptime(d['date'], '%Y-%m-%d'))
                closes.append(float(d['close']))
            except Exception:
                continue
        return dates, closes

    except Exception as e:
        print(f"KOSPI data load failed: {e}, using mock data")
        dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
        closes = [2500 + i * 2 for i in range(days)]
        return dates, closes


# ─── KOSPI Chart ──────────────────────────────────────────────
def generate_kospi_chart_pillow(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """KOSPI technical chart via Pillow (white professional theme)"""
    try:
        dates, closes = load_kospi_data(days)
        if not dates or not closes:
            raise Exception("Empty data")

        width, height = 1400, 660
        pad_l, pad_r, pad_t, pad_b = 90, 50, 55, 65
        cw = width - pad_l - pad_r
        ch = height - pad_t - pad_b

        img = Image.new('RGB', (width, height), BG_WHITE)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()

        # Title
        draw.text((width // 2, 28), "KOSPI Technical Analysis",
                  fill=LINE_NAVY, font=fonts['title'], anchor="mm")

        min_p, max_p = min(closes), max(closes)
        p_range = max_p - min_p if max_p != min_p else 1

        def tx(i):
            return pad_l + int(i / max(1, len(closes) - 1) * cw)

        def ty(p):
            return pad_t + int((max_p - p) / p_range * ch)

        # Grid
        for i in range(5):
            y = pad_t + int(i * ch / 4)
            draw.line([(pad_l, y), (width - pad_r, y)], fill=GRID_LIGHT, width=1)
            price = max_p - (i * p_range / 4)
            draw.text((pad_l - 10, y), f"{price:.0f}",
                      fill=TEXT_MEDIUM, font=fonts['small'], anchor="rm")

        # 20-day MA
        if len(closes) >= 20:
            ma_points = []
            for i in range(19, len(closes)):
                ma = sum(closes[i - 19:i + 1]) / 20
                ma_points.append((tx(i), ty(ma)))
            if len(ma_points) > 1:
                draw.line(ma_points, fill=SLATE + (100,), width=2)

        # Main KOSPI line
        points = [(tx(i), ty(c)) for i, c in enumerate(closes)]
        if len(points) > 1:
            draw.line(points, fill=LINE_NAVY, width=3)

        # Current point
        if points:
            lx, ly = points[-1]
            draw.ellipse([lx - 9, ly - 9, lx + 9, ly + 9], fill=ACCENT_GOLD, outline=LINE_NAVY)
            draw.text((lx, ly - 22), f"{closes[-1]:.0f}",
                      fill=ACCENT_GOLD, font=fonts['value'], anchor="mm")

        # Date labels
        for idx in [0, len(dates) // 4, len(dates) // 2, 3 * len(dates) // 4, len(dates) - 1]:
            if idx < len(dates):
                x = tx(idx)
                draw.text((x, height - pad_b + 20), dates[idx].strftime('%m/%d'),
                          fill=TEXT_MEDIUM, font=fonts['small'], anchor="mm")

        # Legend
        ly = pad_t + 15
        draw.rectangle([pad_l + 5, ly - 12, pad_l + 210, ly + 14], fill=BG_CARD, outline=GRID_LIGHT)
        draw.line([(pad_l + 14, ly), (pad_l + 44, ly)], fill=LINE_NAVY, width=3)
        draw.text((pad_l + 52, ly), "KOSPI", fill=TEXT_DARK, font=fonts['label'], anchor="lm")
        draw.line([(pad_l + 110, ly), (pad_l + 140, ly)], fill=SLATE, width=2)
        draw.text((pad_l + 148, ly), "MA20", fill=TEXT_MEDIUM, font=fonts['small'], anchor="lm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"Pillow KOSPI chart failed: {e}")
        return _error_image(1400, 660)


# ─── Surprise Z-Score Chart ──────────────────────────────────
def generate_surprise_chart_pillow(signal_data: Dict[str, Any], history_days: int = 30) -> bytes:
    """Surprise Z-Score timeline via Pillow"""
    try:
        width, height = 880, 640
        pad_l, pad_r, pad_t, pad_b = 70, 40, 55, 55
        cw = width - pad_l - pad_r
        ch = height - pad_t - pad_b

        img = Image.new('RGB', (width, height), BG_WHITE)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()

        # Generate mock Z-score data
        random.seed(hash(signal_data.get('symbol', '')) % 10000)
        z_scores = [random.gauss(0, 1.2) for _ in range(history_days)]
        z_scores[-1] = signal_data.get('surpriseZ', 0)

        # Title
        symbol = signal_data.get('symbol', 'SYMBOL')
        draw.text((width // 2, 25), f"{symbol} - Surprise Z-Score",
                  fill=LINE_NAVY, font=fonts['title'], anchor="mm")

        # Y range
        y_min = min(min(z_scores) - 0.5, -3)
        y_max = max(max(z_scores) + 0.5, 3)
        y_range = y_max - y_min

        def tx(i):
            return pad_l + int(i / max(1, history_days - 1) * cw)

        def ty(v):
            return pad_t + int((y_max - v) / y_range * ch)

        # Grid + labels
        for val in [-2, -1, 0, 1, 2]:
            if y_min <= val <= y_max:
                y = ty(val)
                if val == 0:
                    draw.line([(pad_l, y), (width - pad_r, y)], fill=TEXT_LIGHT, width=1)
                else:
                    draw.line([(pad_l, y), (width - pad_r, y)], fill=GRID_LIGHT, width=1)
                draw.text((pad_l - 8, y), f"{val:+.0f}",
                          fill=TEXT_MEDIUM, font=fonts['small'], anchor="rm")

        # Threshold dashed lines
        for thresh, color in [(2, SIGNAL_BUY), (-2, SIGNAL_SELL)]:
            if y_min <= thresh <= y_max:
                _draw_dashed_line(draw, (pad_l, ty(thresh)), (width - pad_r, ty(thresh)),
                                  fill=color, width=1)

        # Z-Score fill area (subtle)
        zero_y = ty(0)
        points_above = []
        points_below = []
        for i, z in enumerate(z_scores):
            x = tx(i)
            y = ty(z)
            if z >= 0:
                points_above.append((x, y))
            else:
                points_below.append((x, y))

        # Line
        line_points = [(tx(i), ty(z)) for i, z in enumerate(z_scores)]
        if len(line_points) > 1:
            draw.line(line_points, fill=LINE_NAVY, width=2)

        # Current point
        if line_points:
            lx, ly = line_points[-1]
            r = 8
            draw.ellipse([lx - r, ly - r, lx + r, ly + r],
                         fill=ACCENT_GOLD, outline=LINE_NAVY, width=2)
            draw.text((lx, ly - 18), f"{z_scores[-1]:.2f}",
                      fill=ACCENT_GOLD, font=fonts['value'], anchor="mm")

        # Legend
        lgx, lgy = pad_l + 8, pad_t + 8
        draw.rectangle([lgx, lgy, lgx + 160, lgy + 50], fill=BG_CARD, outline=GRID_LIGHT)
        draw.line([(lgx + 8, lgy + 14), (lgx + 30, lgy + 14)], fill=LINE_NAVY, width=2)
        draw.text((lgx + 36, lgy + 14), "Z-Score", fill=TEXT_DARK, font=fonts['small'], anchor="lm")
        _draw_dashed_line(draw, (lgx + 8, lgy + 36), (lgx + 30, lgy + 36), fill=SIGNAL_BUY, width=1)
        draw.text((lgx + 36, lgy + 36), "Threshold", fill=TEXT_MEDIUM, font=fonts['small'], anchor="lm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"Pillow surprise chart failed: {e}")
        return _error_image(880, 640)


# ─── Performance Comparison Chart ─────────────────────────────
def generate_comparison_chart_pillow(signal_data: Dict[str, Any]) -> bytes:
    """Performance vs KOSPI horizontal bar chart via Pillow"""
    try:
        width, height = 880, 640
        pad_l, pad_r, pad_t, pad_b = 160, 80, 55, 50
        cw = width - pad_l - pad_r
        ch = height - pad_t - pad_b

        img = Image.new('RGB', (width, height), BG_WHITE)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()

        symbol = signal_data.get('symbol', 'SYMBOL')
        draw.text((width // 2, 25), f"{symbol} - vs KOSPI",
                  fill=LINE_NAVY, font=fonts['title'], anchor="mm")

        categories = ['Expected Return', 'KOSPI Return', 'vs KOSPI']
        values = [
            signal_data.get('expectedReturn', 0),
            signal_data.get('kospiReturn', 0),
            signal_data.get('vsKospi', 0),
        ]

        max_abs = max((abs(v) for v in values), default=1) or 1
        bar_h = min(70, ch // len(categories) - 30)
        zero_x = pad_l + cw // 2

        # Zero line
        draw.line([(zero_x, pad_t), (zero_x, height - pad_b)], fill=TEXT_MEDIUM, width=1)

        # Vertical grid
        for frac in [-1, -0.5, 0.5, 1]:
            x = zero_x + int(frac * cw / 2)
            draw.line([(x, pad_t), (x, height - pad_b)], fill=GRID_LIGHT, width=1)
            val = frac * max_abs
            draw.text((x, height - pad_b + 18), f"{val:+.1f}%",
                      fill=TEXT_MEDIUM, font=fonts['small'], anchor="mm")

        for i, (cat, val) in enumerate(zip(categories, values)):
            slot_h = ch // len(categories)
            bar_y = pad_t + i * slot_h + (slot_h - bar_h) // 2
            bar_center_y = bar_y + bar_h // 2

            # Bar
            bar_len = int(val / max_abs * (cw / 2))
            color = SIGNAL_BUY if val >= 0 else SIGNAL_SELL
            if val >= 0:
                draw.rectangle([zero_x, bar_y, zero_x + bar_len, bar_y + bar_h], fill=color)
            else:
                draw.rectangle([zero_x + bar_len, bar_y, zero_x, bar_y + bar_h], fill=color)

            # Category label
            draw.text((pad_l - 12, bar_center_y), cat,
                      fill=TEXT_DARK, font=fonts['label'], anchor="rm")

            # Value label
            if val >= 0:
                lx = zero_x + bar_len + 10
                anchor = "lm"
            else:
                lx = zero_x + bar_len - 10
                anchor = "rm"
            draw.text((lx, bar_center_y), f"{val:+.1f}%",
                      fill=TEXT_DARK, font=fonts['value'], anchor=anchor)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"Pillow comparison chart failed: {e}")
        return _error_image(880, 640)


# ─── Confidence Gauge ─────────────────────────────────────────
def generate_confidence_gauge_pillow(score: float) -> bytes:
    """Confidence semi-circle gauge via Pillow"""
    try:
        width, height = 700, 450
        cx, cy = width // 2, height - 90
        outer_r = 170
        inner_r = 105

        img = Image.new('RGB', (width, height), BG_WHITE)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()

        score = max(0, min(100, score))

        # Title
        draw.text((width // 2, 22), "Model Confidence Score",
                  fill=LINE_NAVY, font=fonts['title'], anchor="mm")

        # Segments: (start%, end%, solid_color)
        segments = [
            (0, 30, SIGNAL_SELL),
            (30, 60, SIGNAL_HOLD),
            (60, 80, SIGNAL_BUY),
            (80, 100, EXCELLENT_GN),
        ]

        # Background arcs (muted)
        for s_pct, e_pct, color in segments:
            s_angle = 180 + int(s_pct / 100 * 180)
            e_angle = 180 + int(e_pct / 100 * 180)
            muted = tuple(min(255, c + 150) for c in color)
            draw.pieslice(
                [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
                s_angle, e_angle, fill=muted
            )

        # Active arcs (filled up to score)
        for s_pct, e_pct, color in segments:
            actual_end = min(e_pct, score)
            if actual_end <= s_pct:
                continue
            s_angle = 180 + int(s_pct / 100 * 180)
            e_angle = 180 + int(actual_end / 100 * 180)
            draw.pieslice(
                [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
                s_angle, e_angle, fill=color
            )

        # Inner circle (donut hole)
        draw.ellipse(
            [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
            fill=BG_WHITE
        )

        # Cover bottom half (below center line)
        draw.rectangle([0, cy, width, height], fill=BG_WHITE)

        # Needle
        angle_deg = 180 + score / 100 * 180
        angle_rad = math.radians(angle_deg)
        needle_len = inner_r - 12
        nx = cx + needle_len * math.cos(angle_rad)
        ny = cy + needle_len * math.sin(angle_rad)
        draw.line([(cx, cy), (int(nx), int(ny))], fill=LINE_NAVY, width=3)

        # Center dot
        dr = 7
        draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=LINE_NAVY)

        # Score color
        if score >= 80:
            sc = EXCELLENT_GN
        elif score >= 60:
            sc = SIGNAL_BUY
        elif score >= 30:
            sc = SIGNAL_HOLD
        else:
            sc = SIGNAL_SELL

        draw.text((cx, cy + 22), f"{score:.0f}%", fill=sc, font=fonts['score'], anchor="mm")
        draw.text((cx, cy + 58), "Confidence", fill=TEXT_MEDIUM, font=fonts['label'], anchor="mm")

        # Scale labels
        draw.text((cx - outer_r - 12, cy + 5), "0",
                  fill=TEXT_MEDIUM, font=fonts['small'], anchor="rm")
        draw.text((cx + outer_r + 12, cy + 5), "100",
                  fill=TEXT_MEDIUM, font=fonts['small'], anchor="lm")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"Pillow gauge failed: {e}")
        return _error_image(700, 450)


# ─── Error Image Helper ──────────────────────────────────────
def _error_image(w=800, h=400):
    """Generate a simple error placeholder image"""
    img = Image.new('RGB', (w, h), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.text((w // 2, h // 2), "Chart generation error",
              fill=SIGNAL_SELL, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
