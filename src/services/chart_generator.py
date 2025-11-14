import matplotlib
matplotlib.use('Agg')  # GUI 없이 사용
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

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


def load_kospi_data(days: int = 60) -> tuple:
    """KOSPI 데이터 로드 (S3 또는 로컬)"""
    try:
        use_s3 = os.environ.get('USE_S3_DATA', 'false').lower() == 'true'

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
            # 로컬
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

        # 데이터 필터링 (유효한 데이터만)
        valid_data = []
        for d in data:
            try:
                if d['date'] and d['close'] > 0:
                    valid_data.append(d)
            except (KeyError, TypeError, ValueError):
                continue

        if not valid_data:
            raise Exception("유효한 KOSPI 데이터가 없습니다")

        # 최근 N일 데이터만 사용
        valid_data = sorted(valid_data, key=lambda x: x['date'])[-days:]

        dates = []
        closes = []
        highs = []
        lows = []

        for d in valid_data:
            try:
                dates.append(datetime.strptime(d['date'], '%Y-%m-%d'))
                closes.append(float(d['close']))
                highs.append(float(d['high']))
                lows.append(float(d['low']))
            except Exception as parse_error:
                print(f"⚠️ 데이터 파싱 오류: {parse_error}")
                continue

        if not dates or not closes:
            raise Exception("날짜 또는 가격 데이터 파싱 실패")

        print(f"✅ KOSPI 데이터 로드 완료: {len(dates)}일")
        return dates, closes, highs, lows

    except Exception as e:
        print(f"⚠️ KOSPI 데이터 로드 실패: {e}")
        # Fallback: Mock 데이터
        dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
        base = 2500
        closes = base + np.cumsum(np.random.randn(days) * 10)
        highs = closes + np.random.rand(days) * 20
        lows = closes - np.random.rand(days) * 20
        return dates, closes.tolist(), highs.tolist(), lows.tolist()


def calculate_support_resistance(prices: List[float], window: int = 5) -> tuple:
    """지지선과 저항선 계산"""
    try:
        if len(prices) < window * 2 + 1:
            # 데이터가 충분하지 않으면 단순 최고/최저
            return min(prices), max(prices)

        highs = []
        lows = []

        for i in range(window, len(prices) - window):
            try:
                # 고점: 양옆보다 높으면
                if all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                   all(prices[i] >= prices[i+j] for j in range(1, window+1)):
                    highs.append(prices[i])

                # 저점: 양옆보다 낮으면
                if all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                   all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                    lows.append(prices[i])
            except (IndexError, TypeError):
                continue

        resistance = float(np.mean(highs)) if highs else float(max(prices))
        support = float(np.mean(lows)) if lows else float(min(prices))

        return support, resistance
    except Exception as e:
        print(f"⚠️ 지지/저항선 계산 오류: {e}")
        # Fallback: 단순 최고/최저
        return float(min(prices)), float(max(prices))


def calculate_trendline(dates: List[datetime], prices: List[float]) -> tuple:
    """추세선 계산 (선형 회귀)"""
    x = np.arange(len(prices))
    coeffs = np.polyfit(x, prices, 1)  # 1차 다항식 (직선)
    trendline = np.polyval(coeffs, x)
    return trendline, coeffs[0]  # trendline, slope


def generate_surprise_chart(signal_data: Dict[str, Any], history_days: int = 30) -> bytes:
    """
    Surprise Z-Score 타임라인 차트 생성 (Dashboard용 간단 차트)
    
    Args:
        signal_data: 시그널 데이터
        history_days: 히스토리 일수
        
    Returns:
        PNG 이미지 바이트
    """
    fig, ax = plt.subplots(figsize=(8, 4), facecolor='#1a1f3a')
    ax.set_facecolor('#0a0e27')
    
    # Mock 데이터 생성 (실제로는 DB에서 가져와야 함)
    dates = [datetime.now() - timedelta(days=i) for i in range(history_days, 0, -1)]
    z_scores = np.random.randn(history_days) * 1.5
    z_scores[-1] = signal_data.get('surpriseZ', 0)  # 현재 값
    
    # 차트 그리기
    ax.plot(dates, z_scores, color='#4c6fff', linewidth=2, label='Surprise Z-Score')
    ax.axhline(y=0, color='#9aa0a6', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(y=2, color='#10b981', linestyle='--', linewidth=1, alpha=0.3, label='Buy Threshold (+2.0)')
    ax.axhline(y=-2, color='#ef4444', linestyle='--', linewidth=1, alpha=0.3, label='Sell Threshold (-2.0)')
    
    # 현재 포인트 강조
    ax.scatter(dates[-1], z_scores[-1], color='#f59e0b', s=100, zorder=5, label='Current')
    
    # 스타일링
    ax.set_xlabel('Date', color='#9aa0a6', fontsize=10)
    ax.set_ylabel('Z-Score', color='#9aa0a6', fontsize=10)
    ax.set_title(f'{signal_data.get("symbol", "SYMBOL")} - Surprise Z-Score History', 
                 color='#e5e7eb', fontsize=12, fontweight='bold')
    
    ax.tick_params(colors='#9aa0a6', labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#2a2f4a')
    ax.spines['bottom'].set_color('#2a2f4a')
    ax.grid(True, alpha=0.1, color='#9aa0a6')
    
    # 범례
    ax.legend(loc='upper left', fontsize=8, framealpha=0.8, facecolor='#1a1f3a', edgecolor='#2a2f4a')
    
    plt.tight_layout()
    
    # 이미지로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#1a1f3a')
    buf.seek(0)
    plt.close()
    
    return buf.getvalue()


def generate_price_chart(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """
    가격 차트 생성 (Reports용 상세 차트)
    
    Args:
        signal_data: 시그널 데이터
        days: 표시 일수
        
    Returns:
        PNG 이미지 바이트
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), facecolor='#1a1f3a', 
                                     gridspec_kw={'height_ratios': [3, 1]})
    
    ax1.set_facecolor('#0a0e27')
    ax2.set_facecolor('#0a0e27')
    
    # Mock 가격 데이터 생성
    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
    base_price = 100
    prices = base_price + np.cumsum(np.random.randn(days) * 2)
    
    # 이동평균선
    ma5 = np.convolve(prices, np.ones(5)/5, mode='valid')
    ma20 = np.convolve(prices, np.ones(20)/20, mode='valid')
    
    # 가격 차트
    ax1.plot(dates, prices, color='#e5e7eb', linewidth=1.5, label='Price')
    ax1.plot(dates[4:], ma5, color='#4c6fff', linewidth=1.5, linestyle='--', label='MA5', alpha=0.8)
    ax1.plot(dates[19:], ma20, color='#10b981', linewidth=1.5, linestyle='--', label='MA20', alpha=0.8)
    
    # 예측 구간 (회색 영역)
    period_days = int(signal_data.get('period', '1d').replace('d', ''))
    future_dates = [dates[-1] + timedelta(days=i) for i in range(1, period_days + 1)]
    expected_return = signal_data.get('expectedReturn', 0) / 100
    future_price = prices[-1] * (1 + expected_return)
    
    ax1.fill_between(
        [dates[-1]] + future_dates,
        [prices[-1]] + [future_price * 0.95] * period_days,
        [prices[-1]] + [future_price * 1.05] * period_days,
        alpha=0.2, color='#9aa0a6', label='Prediction Range'
    )
    
    ax1.set_ylabel('Price', color='#9aa0a6', fontsize=11)
    ax1.set_title(f'{signal_data.get("symbol", "SYMBOL")} - Price & Moving Averages', 
                  color='#e5e7eb', fontsize=13, fontweight='bold')
    ax1.tick_params(colors='#9aa0a6', labelsize=9)
    ax1.legend(loc='upper left', fontsize=9, framealpha=0.8, facecolor='#1a1f3a', edgecolor='#2a2f4a')
    ax1.grid(True, alpha=0.1, color='#9aa0a6')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_color('#2a2f4a')
    ax1.spines['bottom'].set_color('#2a2f4a')
    
    # Surprise Z-Score 히스토리
    z_scores = np.random.randn(days) * 1.5
    z_scores[-1] = signal_data.get('surpriseZ', 0)
    
    colors_list = ['#10b981' if z > 0 else '#ef4444' for z in z_scores]
    ax2.bar(dates, z_scores, color=colors_list, alpha=0.7, width=0.8)
    ax2.axhline(y=0, color='#9aa0a6', linestyle='-', linewidth=1)
    ax2.axhline(y=2, color='#10b981', linestyle='--', linewidth=1, alpha=0.3)
    ax2.axhline(y=-2, color='#ef4444', linestyle='--', linewidth=1, alpha=0.3)
    
    ax2.set_ylabel('Z-Score', color='#9aa0a6', fontsize=10)
    ax2.set_xlabel('Date', color='#9aa0a6', fontsize=10)
    ax2.tick_params(colors='#9aa0a6', labelsize=9)
    ax2.grid(True, alpha=0.1, color='#9aa0a6')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_color('#2a2f4a')
    ax2.spines['bottom'].set_color('#2a2f4a')
    
    plt.tight_layout()
    
    # 이미지로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#1a1f3a')
    buf.seek(0)
    plt.close()
    
    return buf.getvalue()


def generate_kospi_comparison_chart(signal_data: Dict[str, Any]) -> bytes:
    """
    KOSPI 대비 차트 생성

    Args:
        signal_data: 시그널 데이터

    Returns:
        PNG 이미지 바이트
    """
    fig, ax = plt.subplots(figsize=(8, 5), facecolor='#1a1f3a')
    ax.set_facecolor('#0a0e27')

    # 데이터
    categories = ['Expected\nReturn', 'KOSPI\nReturn', 'vs KOSPI']
    values = [
        signal_data.get('expectedReturn', 0),
        signal_data.get('kospiReturn', 0),
        signal_data.get('vsKospi', 0)
    ]
    colors_list = ['#10b981' if v >= 0 else '#ef4444' for v in values]

    # 막대 차트
    bars = ax.bar(categories, values, color=colors_list, alpha=0.8, width=0.6)

    # 값 표시
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{value:+.1f}%',
                ha='center', va='bottom' if height >= 0 else 'top',
                color='#e5e7eb', fontsize=11, fontweight='bold')

    # 0선
    ax.axhline(y=0, color='#9aa0a6', linestyle='-', linewidth=1)

    # 스타일링
    ax.set_ylabel('Return (%)', color='#9aa0a6', fontsize=11)
    ax.set_title(f'{signal_data.get("symbol", "SYMBOL")} - Performance vs KOSPI',
                 color='#e5e7eb', fontsize=12, fontweight='bold')
    ax.tick_params(colors='#9aa0a6', labelsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#2a2f4a')
    ax.spines['bottom'].set_color('#2a2f4a')
    ax.grid(True, alpha=0.1, color='#9aa0a6', axis='y')

    plt.tight_layout()

    # 이미지로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#1a1f3a')
    buf.seek(0)
    plt.close()

    return buf.getvalue()


def generate_kospi_advanced_chart(signal_data: Dict[str, Any], days: int = 60) -> bytes:
    """
    KOSPI 고급 차트 생성 (추세선, 지지/저항선 포함)

    Args:
        signal_data: 시그널 데이터
        days: 표시 일수

    Returns:
        PNG 이미지 바이트
    """
    fig, ax = plt.subplots(figsize=(12, 7), facecolor='#1a1f3a')
    ax.set_facecolor('#0a0e27')

    # KOSPI 데이터 로드
    dates, closes, highs, lows = load_kospi_data(days)

    # 추세선 계산
    trendline, slope = calculate_trendline(dates, closes)

    # 지지선/저항선 계산
    support, resistance = calculate_support_resistance(closes)

    # KOSPI 가격 차트
    ax.plot(dates, closes, color='#4c6fff', linewidth=2.5, label='KOSPI', zorder=3)

    # 추세선
    trend_color = '#10b981' if slope > 0 else '#ef4444'
    ax.plot(dates, trendline, color=trend_color, linewidth=2, linestyle='--',
            label=f'Trend ({"상승" if slope > 0 else "하락"})', alpha=0.8, zorder=2)

    # 지지선
    ax.axhline(y=support, color='#10b981', linestyle=':', linewidth=2,
               label=f'Support {support:.0f}', alpha=0.7)
    ax.fill_between(dates, support - 20, support + 20,
                     color='#10b981', alpha=0.1)

    # 저항선
    ax.axhline(y=resistance, color='#ef4444', linestyle=':', linewidth=2,
               label=f'Resistance {resistance:.0f}', alpha=0.7)
    ax.fill_between(dates, resistance - 20, resistance + 20,
                     color='#ef4444', alpha=0.1)

    # 현재 위치 강조
    ax.scatter(dates[-1], closes[-1], color='#f59e0b', s=200,
               zorder=5, edgecolors='#fff', linewidth=2, label='Current')
    ax.text(dates[-1], closes[-1] + 30, f'{closes[-1]:.0f}',
            ha='center', va='bottom', color='#f59e0b', fontsize=12, fontweight='bold')

    # 이동평균선 (안전하게 계산)
    try:
        if len(closes) >= 20:
            ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
            if len(ma20) > 0 and len(dates) >= 19 + len(ma20):
                ax.plot(dates[19:19+len(ma20)], ma20, color='#818cf8', linewidth=1.5,
                        linestyle='--', label='MA20', alpha=0.6)

        if len(closes) >= 60:
            ma60_window = min(60, len(closes))
            ma60 = np.convolve(closes, np.ones(ma60_window)/ma60_window, mode='valid')
            if len(ma60) > 0 and len(dates) >= ma60_window - 1 + len(ma60):
                ax.plot(dates[ma60_window-1:ma60_window-1+len(ma60)], ma60,
                        color='#c084fc', linewidth=1.5, linestyle='--', label='MA60', alpha=0.6)
    except Exception as ma_error:
        print(f"⚠️ 이동평균선 계산 오류: {ma_error}")

    # 스타일링
    ax.set_xlabel('Date', color='#9aa0a6', fontsize=12)
    ax.set_ylabel('KOSPI Index', color='#9aa0a6', fontsize=12)
    ax.set_title('KOSPI Technical Analysis (Support, Resistance & Trend)',
                 color='#e5e7eb', fontsize=14, fontweight='bold', pad=20)

    ax.tick_params(colors='#9aa0a6', labelsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#2a2f4a')
    ax.spines['bottom'].set_color('#2a2f4a')
    ax.grid(True, alpha=0.15, color='#9aa0a6', linestyle='--')

    # 범례
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9,
              facecolor='#1a1f3a', edgecolor='#2a2f4a')

    # 날짜 포맷 (안전하게 처리)
    try:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    except Exception as date_error:
        print(f"⚠️ 날짜 포맷 오류: {date_error}")

    plt.tight_layout()

    # 이미지로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#1a1f3a')
    buf.seek(0)
    plt.close()

    return buf.getvalue()