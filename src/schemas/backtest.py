from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class BacktestRequest(BaseModel):
    startDate: datetime
    endDate: datetime
    stocks: List[str]
    strategy: str

class BacktestResult(BaseModel):
    avgReturn: float
    winRate: float
    sharpeRatio: float
    maxDrawdown: float

class BacktestResponse(BaseModel):
    jobId: str
    status: str  # "pending" | "running" | "completed" | "failed"
    result: Optional[BacktestResult] = None