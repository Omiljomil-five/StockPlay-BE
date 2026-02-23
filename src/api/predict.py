from fastapi import APIRouter, BackgroundTasks
from datetime import datetime
from typing import Optional
from ..schemas import ApiResponse

router = APIRouter(prefix="/predict", tags=["predict"])

# 마지막 예측 실행 상태
_last_run = {
    "status": "never_run",
    "started_at": None,
    "completed_at": None,
    "symbols_count": 0,
    "rows_count": 0,
    "error": None,
}


def _run_arima_batch():
    """ARIMA 배치 실행 (BackgroundTasks용)"""
    global _last_run
    _last_run["status"] = "running"
    _last_run["started_at"] = datetime.now().isoformat()
    _last_run["error"] = None

    try:
        from ..services.arima_service import get_arima_service
        service = get_arima_service()
        result = service.run_batch()

        _last_run["status"] = "completed"
        _last_run["completed_at"] = datetime.now().isoformat()
        _last_run["symbols_count"] = result['symbol'].nunique() if 'symbol' in result.columns else 0
        _last_run["rows_count"] = len(result)
        print(f"ARIMA 배치 완료: {_last_run['symbols_count']} 종목, {_last_run['rows_count']} 행")
    except Exception as e:
        _last_run["status"] = "failed"
        _last_run["completed_at"] = datetime.now().isoformat()
        _last_run["error"] = str(e)
        print(f"ARIMA 배치 실패: {e}")


@router.post("/run")
async def run_prediction(background_tasks: BackgroundTasks):
    """
    ARIMA 배치 예측 수동 실행.
    백그라운드로 실행되며 /status로 진행 상태 확인 가능.
    """
    if _last_run["status"] == "running":
        return ApiResponse(
            success=False,
            data={"message": "이미 예측이 실행 중입니다", "status": _last_run},
            error="ALREADY_RUNNING"
        )

    background_tasks.add_task(_run_arima_batch)

    return ApiResponse(
        success=True,
        data={
            "message": "ARIMA 배치 예측이 시작되었습니다",
            "started_at": datetime.now().isoformat()
        }
    )


@router.get("/status")
async def get_prediction_status():
    """마지막 예측 실행 시간/상태 조회"""
    return ApiResponse(success=True, data=_last_run)


@router.get("/latest")
async def get_latest_predictions(
    symbol: Optional[str] = None,
    limit: int = 50
):
    """
    최신 ARIMA 예측 결과 조회.

    Args:
        symbol: 특정 종목 필터 (없으면 전체)
        limit: 결과 개수 제한
    """
    try:
        from ..services.arima_service import get_arima_service
        service = get_arima_service()
        df = service.load_latest_predictions()

        if df is None:
            return ApiResponse(
                success=True,
                data={
                    "predictions": [],
                    "message": "아직 ARIMA 예측 결과가 없습니다. POST /api/predict/run으로 실행하세요.",
                    "count": 0
                }
            )

        if symbol:
            df = df[df['symbol'].astype(str).str.strip() == symbol]

        # 최신 날짜만
        if 'date' in df.columns:
            latest_date = df['date'].max()
            df = df[df['date'] == latest_date]

        records = df.head(limit).to_dict('records')

        return ApiResponse(
            success=True,
            data={
                "predictions": records,
                "count": len(records),
                "latest_date": str(latest_date) if 'date' in df.columns else None
            }
        )

    except Exception as e:
        return ApiResponse(
            success=False,
            data={"predictions": [], "count": 0},
            error=str(e)
        )
