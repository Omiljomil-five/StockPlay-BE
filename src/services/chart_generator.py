import matplotlib
matplotlib.use('Agg')  # GUI 없이 사용
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import base64
from typing import List, Dict, Any
import numpy as np

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


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