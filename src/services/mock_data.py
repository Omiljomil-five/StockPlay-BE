from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

def generate_mock_signals(limit: int = 20, sector: str = None) -> List[Dict[str, Any]]:
    """Mock 트레이딩 시그널 생성"""
    
    stocks = [
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "IT"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "임의소비재"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "IT"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "IT"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "통신서비스"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "임의소비재"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "통신서비스"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "IT"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "통신서비스"},
        {"symbol": "DIS", "name": "The Walt Disney Company", "sector": "통신서비스"},
        {"symbol": "BA", "name": "Boeing Company", "sector": "산업재"},
        {"symbol": "NKE", "name": "NIKE Inc.", "sector": "임의소비재"},
        {"symbol": "SBUX", "name": "Starbucks Corporation", "sector": "임의소비재"},
        {"symbol": "XOM", "name": "Exxon Mobil Corporation", "sector": "에너지"},
        {"symbol": "CVX", "name": "Chevron Corporation", "sector": "에너지"},
        {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "헬스케어"},
        {"symbol": "PFE", "name": "Pfizer Inc.", "sector": "헬스케어"},
        {"symbol": "WMT", "name": "Walmart Inc.", "sector": "필수소비재"},
        {"symbol": "PG", "name": "Procter & Gamble", "sector": "필수소비재"},
        {"symbol": "KO", "name": "The Coca-Cola Company", "sector": "필수소비재"},
    ]
    
    # 섹터 필터링
    if sector:
        stocks = [s for s in stocks if s["sector"] == sector]
    
    signals = []
    for i, stock in enumerate(stocks[:limit]):
        signals.append({
            "id": f"signal-{i+1}",
            "symbol": stock["symbol"],
            "companyName": stock["name"],
            "sector": stock["sector"],
            "signalType": "BUY",
            "yoyGrowth": round(random.uniform(15, 25), 1),
            "momGrowth": round(random.uniform(8, 18), 1),
            "expectedReturn": round(random.uniform(10, 20), 1),
            "confidenceScore": round(random.uniform(75, 95), 1),
        })
    
    return signals

def generate_mock_analysis(limit: int = 20, sector: str = None) -> Dict[str, Any]:
    """Mock 분석 결과 생성"""
    
    signals = generate_mock_signals(limit, sector)
    
    return {
        "date": datetime.now().isoformat(),
        "topPicks": signals,
        "performance": {
            "avgReturn": 11.2,
            "winRate": 75.3,
            "sharpeRatio": 1.8,
            "maxDrawdown": -8.5,
        },
        "sectorAnalysis": [
            {"sector": "IT", "avgYoYGrowth": 22.5, "avgMoMGrowth": 12.8, "signalCount": 6, "color": "#4c6fff"},
            {"sector": "통신서비스", "avgYoYGrowth": 18.3, "avgMoMGrowth": 10.2, "signalCount": 4, "color": "#10b981"},
            {"sector": "임의소비재", "avgYoYGrowth": 15.7, "avgMoMGrowth": 8.9, "signalCount": 4, "color": "#f59e0b"},
            {"sector": "산업재", "avgYoYGrowth": 14.2, "avgMoMGrowth": 7.5, "signalCount": 2, "color": "#ef4444"},
            {"sector": "에너지", "avgYoYGrowth": 12.8, "avgMoMGrowth": 6.3, "signalCount": 2, "color": "#818cf8"},
            {"sector": "헬스케어", "avgYoYGrowth": 11.5, "avgMoMGrowth": 5.8, "signalCount": 2, "color": "#ec4899"},
            {"sector": "필수소비재", "avgYoYGrowth": 9.2, "avgMoMGrowth": 4.2, "signalCount": 3, "color": "#8b5cf6"},
        ],
        "totalSignals": len(signals),
    }

def generate_mock_reports(limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """Mock 리포트 목록 생성"""
    
    reports = []
    for i in range(6):  # 6개월치
        month_ago = datetime.now() - timedelta(days=30 * i)
        report_id = f"report-2024-{11-i:02d}"
        
        reports.append({
            "id": report_id,
            "date": month_ago.isoformat(),
            "pdfUrl": f"/reports/{report_id}.pdf",
            "analysisResult": generate_mock_analysis(20),
            "createdAt": month_ago.isoformat(),
        })
    
    # 페이지네이션
    total = len(reports)
    paginated = reports[offset:offset + limit]
    has_more = offset + limit < total
    
    return {
        "reports": paginated,
        "total": total,
        "hasMore": has_more,
    }