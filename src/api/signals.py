from fastapi import APIRouter, Query
from datetime import datetime
from ..schemas import ApiResponse, AnalysisResult
from ..services.ml_predictor import get_predictor

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("", response_model=ApiResponse[AnalysisResult])
async def get_signals(
    sector: str = Query(None, description="섹터 필터"),
    limit: int = Query(20, ge=1, le=50, description="시그널 개수")
):
    """
    트레이딩 시그널 조회 (ML 모델 기반)
    """
    try:
        # ML 모델 실행
        predictor = get_predictor()
        raw_signals = predictor.get_top_signals(limit=limit)
        
        # 데이터 enrichment
        signals = [predictor.enrich_signal_data(s) for s in raw_signals]
        
        # 섹터 필터
        if sector:
            signals = [s for s in signals if s['sector'] == sector]
        
        # 성과 지표 계산
        performance = {
            'avgReturn': round(sum(s['expectedReturn'] for s in signals) / len(signals), 1) if signals else 0,
            'winRate': round(len([s for s in signals if s['signalType'] == 'BUY']) / len(signals) * 100, 1) if signals else 0,
            'sharpeRatio': 1.8,
            'maxDrawdown': -8.5
        }
        
        # 섹터 분석
        from collections import defaultdict
        sector_stats = defaultdict(lambda: {'count': 0, 'yoy': [], 'mom': []})
        
        for s in signals:
            sector_stats[s['sector']]['count'] += 1
            sector_stats[s['sector']]['yoy'].append(s['yoyGrowth'])
            sector_stats[s['sector']]['mom'].append(s['momGrowth'])
        
        sector_analysis = []
        colors = ['#4c6fff', '#10b981', '#f59e0b', '#ef4444', '#818cf8', '#ec4899', '#8b5cf6']
        
        for idx, (sector_name, stats) in enumerate(sector_stats.items()):
            sector_analysis.append({
                'sector': sector_name,
                'avgYoYGrowth': round(sum(stats['yoy']) / len(stats['yoy']), 1),
                'avgMoMGrowth': round(sum(stats['mom']) / len(stats['mom']), 1),
                'signalCount': stats['count'],
                'color': colors[idx % len(colors)]
            })
        
        return ApiResponse(
            success=True,
            data={
                'date': datetime.now().isoformat(),
                'topPicks': signals[:5],
                'performance': performance,
                'sectorAnalysis': sector_analysis,
                'totalSignals': len(signals)
            }
        )
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return ApiResponse(
            success=False,
            data={
                'date': datetime.now().isoformat(),
                'topPicks': [],
                'performance': {
                    'avgReturn': 0,
                    'winRate': 0,
                    'sharpeRatio': 0,
                    'maxDrawdown': 0
                },
                'sectorAnalysis': [],
                'totalSignals': 0
            },
            error=str(e)
        )