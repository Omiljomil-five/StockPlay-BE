import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import base64
from typing import List, Dict, Any, Optional
import numpy as np
import os
import csv
from io import StringIO
import traceback

# ─── White Professional Theme ─────────────────────────────────
PRIMARY_NAVY    = '#1B2A4A'
SECONDARY_SLATE = '#3D5A80'
ACCENT_GOLD     = '#C9A96E'
TEXT_DARK        = '#2C3E50'
TEXT_MEDIUM      = '#5D6D7E'
TEXT_LIGHT       = '#95A5A6'
GRID_COLOR       = '#E5E8EB'
SIGNAL_BUY       = '#0E7C47'
SIGNAL_SELL      = '#C0392B'
SIGNAL_HOLD      = '#D4A017'
MA20_COLOR       = '#7FB3D8'
MA60_COLOR       = '#B0C4DE'
WHITE            = '#FFFFFF'
BG_CARD          = '#F8F9FA'

try:
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"Font config failed: {e}")
    pass


def _style_axes(ax, title='', xlabel='', ylabel=''):
    """Apply consistent white professional styling to axes"""
    ax.set_facecolor(WHITE)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRID_COLOR)
    ax.spines['bottom'].set_color(GRID_COLOR)
    ax.tick_params(colors=TEXT_MEDIUM, labelsize=9)
    ax.grid(True, alpha=0.3, color=GRID_COLOR, linestyle='--')
    if title:
        ax.set_title(title, color=PRIMARY_NAVY, fontsize=12, fontweight='bold', pad=15)
    if xlabel:
        ax.set_xlabel(xlabel, color=TEXT_MEDIUM, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXT_MEDIUM, fontsize=10)


def _save_chart(fig, dpi=200):
    """Save chart to bytes with consistent settings"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi, facecolor=WHITE, bbox_inches='tight')
    buf.seek(0)
    result = buf.getvalue()
    plt.close(fig)
    return result


def load_kospi_data(days: int = 60) -> tuple:
    """KOSPI data loader (S3 or local)"""
    try:
        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'
        print(f"KOSPI data load: {'S3' if use_s3 else 'local'} (days={days})")

        if use_s3:
            import boto3
            s3_bucket = os.getenv('S3_DATA_BUCKET', 'stockplay-data-yjw-20251113')
            s3 = boto3.client('s3')
            obj = s3.get_object(Bucket=s3_bucket, Key='data/kospi.csv')
            csv_content = obj['Body'].read().decode('utf-8-sig')
            reader = csv.DictReader(StringIO(csv_content))
            data = []
            for row in reader:
                data.append({
                    'date': row.get('date', '').strip(),
                    'close': float(row.get('close', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0)),
                    'open': float(row.get('open', 0))
                })
        else:
            from pathlib import Path
            data_path = Path(__file__).parent.parent.parent / 'data' / 'kospi.csv'
            with open(data_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = []
                for row in reader:
                    data.append({
                        'date': row.get('date', '').strip(),
                        'close': float(row.get('close', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'open': float(row.get('open', 0))
                    })

        valid_data = [d for d in data if d.get('date') and d.get('close', 0) > 0]
        if not valid_data:
            raise Exception("No valid KOSPI data")

        valid_data = sorted(valid_data, key=lambda x: x['date'])[-days:]

        dates, closes, highs, lows = [], [], [], []
        for d in valid_data:
            try:
                dates.append(datetime.strptime(d['date'], '%Y-%m-%d'))
                closes.append(float(d['close']))
                highs.append(float(d['high']))
                lows.append(float(d['low']))
            except Exception:
                continue

        if not dates or not closes:
            raise Exception("Date/price parsing failed")

        print(f"KOSPI data loaded: {len(dates)} days")
        return dates, closes, highs, lows

    except Exception as e:
        print(f"KOSPI data load failed: {e}")
        dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
        base = 2500
        closes = base + np.cumsum(np.random.randn(days) * 10)
        highs = closes + np.random.rand(days) * 20
        lows = closes - np.random.rand(days) * 20
        return dates, closes.tolist(), highs.tolist(), lows.tolist()


def calculate_support_resistance(prices: List[float], window: int = 5) -> tuple:
    """Support and resistance levels"""
    try:
        if len(prices) < window * 2 + 1:
            return min(prices), max(prices)

        highs, lows = [], []
        for i in range(window, len(prices) - window):
            try:
                if all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                   all(prices[i] >= prices[i+j] for j in range(1, window+1)):
                    highs.append(prices[i])
                if all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                   all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                    lows.append(prices[i])
            except (IndexError, TypeError):
                continue

        resistance = float(np.mean(highs)) if highs else float(max(prices))
        support = float(np.mean(lows)) if lows else float(min(prices))
        return support, resistance
    except Exception:
        return float(min(prices)), float(max(prices))


def calculate_trendline(dates: List[datetime], prices: List[float]) -> tuple:
    """Linear regression trendline"""
    x = np.arange(len(prices))
    coeffs = np.polyfit(x, prices, 1)
    trendline = np.polyval(coeffs, x)
    return trendline, coeffs[0]


def generate_surprise_chart(signal_data: Dict[str, Any], history_days: int = 30) -> bytes:
    """Surprise Z-Score timeline chart (white professional theme)"""
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=WHITE)

    dates = [datetime.now() - timedelta(days=i) for i in range(history_days, 0, -1)]
    z_scores = np.random.randn(history_days) * 1.5
    z_scores[-1] = signal_data.get('surpriseZ', 0)

    ax.plot(dates, z_scores, color=PRIMARY_NAVY, linewidth=2, label='Surprise Z-Score')
    ax.axhline(y=0, color=TEXT_LIGHT, linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(y=2, color=SIGNAL_BUY, linestyle='--', linewidth=1, alpha=0.25,
               label='Buy Threshold (+2.0)')
    ax.axhline(y=-2, color=SIGNAL_SELL, linestyle='--', linewidth=1, alpha=0.25,
               label='Sell Threshold (-2.0)')

    # Fill zones
    ax.fill_between(dates, 2, max(z_scores.max(), 2.5), alpha=0.04, color=SIGNAL_BUY)
    ax.fill_between(dates, min(z_scores.min(), -2.5), -2, alpha=0.04, color=SIGNAL_SELL)

    ax.scatter(dates[-1], z_scores[-1], color=ACCENT_GOLD, s=100, zorder=5,
               edgecolors=PRIMARY_NAVY, linewidth=1.5, label='Current')

    _style_axes(ax,
                title=f'{signal_data.get("symbol", "SYMBOL")} - Surprise Z-Score History',
                xlabel='Date', ylabel='Z-Score')

    ax.legend(loc='upper left', fontsize=8, framealpha=0.9,
              facecolor=WHITE, edgecolor=GRID_COLOR)
    plt.tight_layout()
    return _save_chart(fig)


def generate_price_chart(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """Price chart with moving averages (white professional theme)"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), facecolor=WHITE,
                                     gridspec_kw={'height_ratios': [3, 1]})

    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
    base_price = 100
    prices = base_price + np.cumsum(np.random.randn(days) * 2)

    ma5 = np.convolve(prices, np.ones(5)/5, mode='valid')
    ma20 = np.convolve(prices, np.ones(20)/20, mode='valid')

    ax1.plot(dates, prices, color=PRIMARY_NAVY, linewidth=1.5, label='Price')
    ax1.plot(dates[4:], ma5, color=SECONDARY_SLATE, linewidth=1.5, linestyle='--',
             label='MA5', alpha=0.7)
    ax1.plot(dates[19:], ma20, color=MA20_COLOR, linewidth=1.5, linestyle='--',
             label='MA20', alpha=0.7)

    period_days = int(signal_data.get('period', '1d').replace('d', ''))
    future_dates = [dates[-1] + timedelta(days=i) for i in range(1, period_days + 1)]
    expected_return = signal_data.get('expectedReturn', 0) / 100
    future_price = prices[-1] * (1 + expected_return)
    ax1.fill_between(
        [dates[-1]] + future_dates,
        [prices[-1]] + [future_price * 0.95] * period_days,
        [prices[-1]] + [future_price * 1.05] * period_days,
        alpha=0.08, color=SECONDARY_SLATE, label='Prediction Range'
    )

    _style_axes(ax1,
                title=f'{signal_data.get("symbol", "SYMBOL")} - Price & Moving Averages',
                ylabel='Price')
    ax1.legend(loc='upper left', fontsize=9, framealpha=0.9,
               facecolor=WHITE, edgecolor=GRID_COLOR)

    # Z-Score subplot
    z_scores = np.random.randn(days) * 1.5
    z_scores[-1] = signal_data.get('surpriseZ', 0)
    bar_colors = [SIGNAL_BUY if z > 0 else SIGNAL_SELL for z in z_scores]
    ax2.bar(dates, z_scores, color=bar_colors, alpha=0.7, width=0.8)
    ax2.axhline(y=0, color=TEXT_LIGHT, linestyle='-', linewidth=1)
    ax2.axhline(y=2, color=SIGNAL_BUY, linestyle='--', linewidth=1, alpha=0.25)
    ax2.axhline(y=-2, color=SIGNAL_SELL, linestyle='--', linewidth=1, alpha=0.25)

    _style_axes(ax2, xlabel='Date', ylabel='Z-Score')

    plt.tight_layout()
    return _save_chart(fig)


def generate_kospi_comparison_chart(signal_data: Dict[str, Any]) -> bytes:
    """Performance vs KOSPI horizontal bar chart (white professional theme)"""
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=WHITE)

    categories = ['Expected\nReturn', 'KOSPI\nReturn', 'vs KOSPI']
    values = [
        signal_data.get('expectedReturn', 0),
        signal_data.get('kospiReturn', 0),
        signal_data.get('vsKospi', 0)
    ]
    bar_colors = [SIGNAL_BUY if v >= 0 else SIGNAL_SELL for v in values]

    bars = ax.barh(categories, values, color=bar_colors, alpha=0.85, height=0.5,
                   edgecolor=WHITE, linewidth=0.5)

    for bar, value in zip(bars, values):
        width = bar.get_width()
        x_pos = width + 0.3 if width >= 0 else width - 0.3
        ha = 'left' if width >= 0 else 'right'
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f'{value:+.1f}%', ha=ha, va='center',
                color=TEXT_DARK, fontsize=11, fontweight='bold')

    ax.axvline(x=0, color=TEXT_LIGHT, linestyle='-', linewidth=1)

    _style_axes(ax,
                title=f'{signal_data.get("symbol", "SYMBOL")} - Performance vs KOSPI',
                xlabel='Return (%)')

    plt.tight_layout()
    return _save_chart(fig)


def generate_kospi_advanced_chart(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """KOSPI advanced technical chart (white professional theme)"""
    print(f"KOSPI chart generation start (days={days})")

    try:
        fig, ax = plt.subplots(figsize=(12, 6), facecolor=WHITE)
    except Exception as e:
        print(f"Figure creation failed: {e}")
        traceback.print_exc()
        raise

    try:
        dates, closes, highs, lows = load_kospi_data(days)
    except Exception as e:
        print(f"KOSPI data load failed: {e}")
        traceback.print_exc()
        plt.close(fig)
        raise

    trendline, slope = calculate_trendline(dates, closes)
    support, resistance = calculate_support_resistance(closes)

    # KOSPI price line
    ax.plot(dates, closes, color=PRIMARY_NAVY, linewidth=2.5, label='KOSPI', zorder=3)

    # Trendline
    trend_color = SIGNAL_BUY if slope > 0 else SIGNAL_SELL
    trend_label = 'Uptrend' if slope > 0 else 'Downtrend'
    ax.plot(dates, trendline, color=trend_color, linewidth=1.5, linestyle='--',
            label=f'Trend ({trend_label})', alpha=0.6, zorder=2)

    # Support line
    ax.axhline(y=support, color=SIGNAL_BUY, linestyle=':', linewidth=1.5,
               label=f'Support {support:.0f}', alpha=0.5)
    ax.fill_between(dates, support - 20, support + 20, color=SIGNAL_BUY, alpha=0.04)

    # Resistance line
    ax.axhline(y=resistance, color=SIGNAL_SELL, linestyle=':', linewidth=1.5,
               label=f'Resistance {resistance:.0f}', alpha=0.5)
    ax.fill_between(dates, resistance - 20, resistance + 20, color=SIGNAL_SELL, alpha=0.04)

    # Current point (gold accent)
    ax.scatter(dates[-1], closes[-1], color=ACCENT_GOLD, s=160,
               zorder=5, edgecolors=PRIMARY_NAVY, linewidth=2, label='Current')
    ax.text(dates[-1], closes[-1] + 25, f'{closes[-1]:.0f}',
            ha='center', va='bottom', color=ACCENT_GOLD, fontsize=11, fontweight='bold')

    # Moving averages
    try:
        if len(closes) >= 20:
            ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
            if len(ma20) > 0 and len(dates) >= 19 + len(ma20):
                ax.plot(dates[19:19+len(ma20)], ma20, color=MA20_COLOR, linewidth=1.5,
                        linestyle='--', label='MA20', alpha=0.6)
        if len(closes) >= 60:
            ma60_window = min(60, len(closes))
            ma60 = np.convolve(closes, np.ones(ma60_window)/ma60_window, mode='valid')
            if len(ma60) > 0 and len(dates) >= ma60_window - 1 + len(ma60):
                ax.plot(dates[ma60_window-1:ma60_window-1+len(ma60)], ma60,
                        color=MA60_COLOR, linewidth=1.5, linestyle='--', label='MA60', alpha=0.6)
    except Exception as e:
        print(f"MA calculation error: {e}")

    _style_axes(ax,
                title='KOSPI Technical Analysis (Support, Resistance & Trend)',
                xlabel='Date', ylabel='KOSPI Index')

    ax.legend(loc='upper left', fontsize=9, framealpha=0.95,
              facecolor=WHITE, edgecolor=GRID_COLOR)

    try:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    except Exception:
        pass

    plt.tight_layout()

    try:
        result = _save_chart(fig)
        print(f"Chart saved: {len(result)} bytes")
        return result
    except Exception as e:
        print(f"Chart save failed: {e}")
        traceback.print_exc()
        plt.close(fig)
        raise


def generate_signal_distribution_chart(signals: List[Dict[str, Any]]) -> bytes:
    """Signal distribution donut chart (white professional theme)"""
    fig, ax = plt.subplots(figsize=(6, 6), facecolor=WHITE)

    buy_count = sum(1 for s in signals if s.get('signalType') == 'BUY')
    hold_count = sum(1 for s in signals if s.get('signalType') == 'HOLD')
    sell_count = sum(1 for s in signals if s.get('signalType') == 'SELL')

    counts = [buy_count, hold_count, sell_count]
    labels = ['BUY', 'HOLD', 'SELL']
    chart_colors = [SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SELL]

    filtered = [(c, l, col) for c, l, col in zip(counts, labels, chart_colors) if c > 0]
    if not filtered:
        filtered = [(1, 'No Data', TEXT_LIGHT)]

    counts_f, labels_f, colors_f = zip(*filtered)

    wedges, texts, autotexts = ax.pie(
        counts_f, labels=labels_f, colors=colors_f,
        autopct='%1.0f%%', startangle=90, pctdistance=0.75,
        wedgeprops=dict(width=0.4, edgecolor=WHITE, linewidth=2)
    )

    for text in texts:
        text.set_color(TEXT_DARK)
        text.set_fontsize(12)
        text.set_fontweight('bold')
    for autotext in autotexts:
        autotext.set_color(TEXT_DARK)
        autotext.set_fontsize(11)

    total = sum(counts_f)
    ax.text(0, 0, f'{total}\nSignals', ha='center', va='center',
            fontsize=16, fontweight='bold', color=PRIMARY_NAVY)

    ax.set_title('Signal Distribution', color=PRIMARY_NAVY, fontsize=14,
                 fontweight='bold', pad=20)

    plt.tight_layout()
    return _save_chart(fig)


def generate_sector_performance_chart(sector_data: List[Dict[str, Any]]) -> bytes:
    """Sector performance horizontal bar chart (white professional theme)"""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=WHITE)

    if not sector_data:
        sector_data = [{'sector': 'No Data', 'avgReturn': 0}]

    sector_data = sorted(sector_data, key=lambda x: x.get('avgReturn', 0))

    sectors = [d['sector'] for d in sector_data]
    returns = [d.get('avgReturn', 0) for d in sector_data]
    bar_colors = [SIGNAL_BUY if r >= 0 else SIGNAL_SELL for r in returns]

    bars = ax.barh(sectors, returns, color=bar_colors, alpha=0.85, height=0.6,
                   edgecolor=WHITE, linewidth=0.5)

    for bar, value in zip(bars, returns):
        width = bar.get_width()
        x_pos = width + 0.2 if width >= 0 else width - 0.2
        ha = 'left' if width >= 0 else 'right'
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f'{value:+.1f}%', ha=ha, va='center',
                color=TEXT_DARK, fontsize=10, fontweight='bold')

    ax.axvline(x=0, color=TEXT_LIGHT, linestyle='-', linewidth=1)

    _style_axes(ax,
                title='Sector Performance',
                xlabel='Avg Expected Return (%)')

    plt.tight_layout()
    return _save_chart(fig)


def generate_confidence_gauge(score: float) -> bytes:
    """Confidence gauge chart (white professional theme)"""
    fig, ax = plt.subplots(figsize=(6, 4), facecolor=WHITE)

    score = max(0, min(100, score))

    segments = [
        (0, 30, SIGNAL_SELL),
        (30, 60, SIGNAL_HOLD),
        (60, 80, SIGNAL_BUY),
        (80, 100, '#0A6B3D'),
    ]

    # Background arcs (muted)
    for start, end, color in segments:
        theta_start = np.pi * (1 - end / 100)
        theta_end = np.pi * (1 - start / 100)
        theta = np.linspace(theta_start, theta_end, 50)
        x_outer = 1.0 * np.cos(theta)
        y_outer = 1.0 * np.sin(theta)
        x_inner = 0.6 * np.cos(theta)
        y_inner = 0.6 * np.sin(theta)
        ax.fill(
            np.concatenate([x_outer, x_inner[::-1]]),
            np.concatenate([y_outer, y_inner[::-1]]),
            color=color, alpha=0.12
        )

    # Filled arcs (active portion)
    for start, end, color in segments:
        actual_end = min(end, score)
        if actual_end <= start:
            continue
        theta_start = np.pi * (1 - actual_end / 100)
        theta_end = np.pi * (1 - start / 100)
        theta = np.linspace(theta_start, theta_end, 50)
        x_outer = 1.0 * np.cos(theta)
        y_outer = 1.0 * np.sin(theta)
        x_inner = 0.6 * np.cos(theta)
        y_inner = 0.6 * np.sin(theta)
        ax.fill(
            np.concatenate([x_outer, x_inner[::-1]]),
            np.concatenate([y_outer, y_inner[::-1]]),
            color=color, alpha=0.85
        )

    # Navy needle
    needle_angle = np.pi * (1 - score / 100)
    ax.plot([0, 0.55 * np.cos(needle_angle)], [0, 0.55 * np.sin(needle_angle)],
            color=PRIMARY_NAVY, linewidth=3, solid_capstyle='round')
    ax.plot(0, 0, 'o', color=PRIMARY_NAVY, markersize=8, zorder=5)

    # Score text
    if score >= 80:
        score_color = '#0A6B3D'
    elif score >= 60:
        score_color = SIGNAL_BUY
    elif score >= 30:
        score_color = SIGNAL_HOLD
    else:
        score_color = SIGNAL_SELL

    ax.text(0, -0.15, f'{score:.0f}%', ha='center', va='center',
            fontsize=28, fontweight='bold', color=score_color)
    ax.text(0, -0.35, 'Confidence', ha='center', va='center',
            fontsize=12, color=TEXT_MEDIUM)

    ax.text(-1.05, -0.05, '0', ha='center', color=TEXT_MEDIUM, fontsize=9)
    ax.text(1.05, -0.05, '100', ha='center', color=TEXT_MEDIUM, fontsize=9)

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.5, 1.15)
    ax.set_aspect('equal')
    ax.axis('off')

    ax.set_title('Model Confidence Score', color=PRIMARY_NAVY, fontsize=14,
                 fontweight='bold', pad=10)

    plt.tight_layout()
    return _save_chart(fig)
