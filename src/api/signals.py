from fastapi import APIRouter, Query
from typing import Optional
from ..schemas import ApiResponse, AnalysisResult, SignalsQueryParams
from ..services.ml_predictor import get_predictor

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("", response_model=ApiResponse[AnalysisResult])
async def get_signals(
    sector: Optional[str] = Query(None, description="섹터 필터"),
    period: str = Query("1d", description="예측 기간 (1d, 5d, 10d, 20d)"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수")
):
    """
    최신 트레이딩 시그널 조회 (기간별 예측 지원)
    
    - **period**: 1d(1일), 5d(5일), 10d(10일), 20d(20일)
    """
    
    try:
        # 실제 ML 모델 사용 (기간 파라미터 추가)
        predictor = get_predictor()
        raw_signals = predictor.get_top_signals(limit=limit, period=period)
        
        # 시그널 데이터 enrichment
        enriched_signals = []
        for signal in raw_signals:
            enriched = predictor.enrich_signal_data(signal)
            if sector is None or enriched['sector'] == sector:
                enriched_signals.append(enriched)
        
        # 섹터별 분석 (MoM 추가)
        sector_stats = {}
        for signal in enriched_signals:
            s = signal['sector']
            if s not in sector_stats:
                sector_stats[s] = {'count': 0, 'total_yoy': 0.0, 'total_mom': 0.0}
            sector_stats[s]['count'] += 1
            sector_stats[s]['total_yoy'] += signal['yoyGrowth']
            sector_stats[s]['total_mom'] += signal.get('momGrowth', 0.0)

        # 섹터 분석 결과
        sector_analysis = []
        sector_colors = {
            '반도체': '#4c6fff', '자동차': '#10b981', '조선': '#f59e0b',
            '바이오': '#ec4899', '기계': '#818cf8', '철강': '#ef4444',
            '석유화학': '#8b5cf6', '디스플레이': '#06b6d4',
        }

        for sector_name, stats in sector_stats.items():
            count = stats['count']
            sector_analysis.append({
                'sector': sector_name,
                'avgYoYGrowth': round(stats['total_yoy'] / count, 1),
                'avgMoMGrowth': round(stats['total_mom'] / count, 1),
                'signalCount': count,
                'color': sector_colors.get(sector_name, '#6b7280'),
                'period': period
            })
        
        # 성과 계산
        if enriched_signals:
            avg_return = sum(s['expectedReturn'] for s in enriched_signals) / len(enriched_signals)
        else:
            avg_return = 0

        # 응답 데이터 구성
        from datetime import datetime
        result = {
            'date': datetime.now().isoformat(),
            'topPicks': enriched_signals[:limit],
            'performance': {
                'avgReturn': round(avg_return, 1),
                'winRate': 66.7,
                'sharpeRatio': 0.76,
                'maxDrawdown': -3.61,
                'period': period
            },
            'sectorAnalysis': sector_analysis,
            'totalSignals': len(enriched_signals)
        }
        
        return ApiResponse(success=True, data=result)
        
    except Exception as e:
        print(f"❌ ML 모델 예측 실패: {e}")
        import traceback
        traceback.print_exc()
        
        from datetime import datetime
        return ApiResponse(
            success=False, 
            data={
                'date': datetime.now().isoformat(),
                'topPicks': [],
                'performance': {'avgReturn': 0, 'winRate': 0, 'sharpeRatio': 0, 'maxDrawdown': 0, 'period': period},
                'sectorAnalysis': [],
                'totalSignals': 0
            }, 
            error=str(e)
        )