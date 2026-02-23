from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TradingSignal(BaseModel):
    id: str
    symbol: str
    companyName: str
    sector: str
    signalType: str  # "BUY" | "HOLD" | "SELL"
    surpriseZ: Optional[float] = 0.0
    yoyGrowth: float
    expectedReturn: float
    vsKospi: Optional[float] = 0.0
    kospiReturn: Optional[float] = 0.0
    confidenceScore: float
    period: Optional[str] = "1d"

class PerformanceMetrics(BaseModel):
    avgReturn: float
    winRate: float
    sharpeRatio: float
    maxDrawdown: float
    period: Optional[str] = "1d"  # 기간 추가

class SectorAnalysis(BaseModel):
    sector: str
    avgYoYGrowth: float  # YoY 유지
    # avgMoMGrowth 제거!
    signalCount: int
    color: str
    period: Optional[str] = "1d"  # 기간 추가

class AnalysisResult(BaseModel):
    date: datetime
    topPicks: List[TradingSignal]
    performance: PerformanceMetrics
    sectorAnalysis: List[SectorAnalysis]
    totalSignals: int

class SignalsQueryParams(BaseModel):
    sector: Optional[str] = None
    period: Optional[str] = "1d"  # 기간 추가
    limit: Optional[int] = 20