from pydantic import BaseModel
from typing import List
from datetime import datetime
from .signal import AnalysisResult

class Report(BaseModel):
    id: str
    date: datetime
    pdfUrl: str
    analysisResult: AnalysisResult
    createdAt: datetime

class ReportsQueryParams(BaseModel):
    limit: int = 10
    offset: int = 0

class ReportsResponse(BaseModel):
    reports: List[Report]
    total: int
    hasMore: bool

class DownloadResponse(BaseModel):
    url: str
    expiresIn: int