from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TradingSignal(BaseModel):
    id: str
    symbol: str
    companyName: str
    sector: str
    signalType: str  # "BUY" | "SELL"
    yoyGrowth: float
    momGrowth: float
    expectedReturn: float
    confidenceScore: float

class PerformanceMetrics(BaseModel):
    avgReturn: float
    winRate: float
    sharpeRatio: float
    maxDrawdown: float

class SectorAnalysis(BaseModel):
    sector: str
    avgYoYGrowth: float
    avgMoMGrowth: float
    signalCount: int
    color: str

class AnalysisResult(BaseModel):
    date: datetime
    topPicks: List[TradingSignal]
    performance: PerformanceMetrics
    sectorAnalysis: List[SectorAnalysis]
    totalSignals: int

class SignalsQueryParams(BaseModel):
    sector: Optional[str] = None
    limit: Optional[int] = 20