from pydantic import BaseModel
from typing import List, Optional
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
    filename: Optional[str] = None  # 파일명 추가
    contentType: str = "application/pdf"  # Content-Type 명시

class PdfGenerationRequest(BaseModel):
    """PDF 생성 요청"""
    symbol: str
    companyName: Optional[str] = None  # 회사명 (선택적, 없으면 자동 생성)
    sector: str
    signalType: str
    period: str
    expectedReturn: float
    vsKospi: float
    kospiReturn: float
    surpriseZ: float
    yoyGrowth: float
    confidenceScore: float

class PdfGenerationResponse(BaseModel):
    """PDF 생성 응답"""
    url: str
    filename: str
    message: str
    ai_used: bool = False