"""
ARIMA 배치 예측 Lambda 핸들러.
매월 1일 10:00 KST (01:00 UTC) 실행.
"""
import json
from datetime import datetime


def lambda_handler(event, context):
    print(f"ARIMA 배치 시작: {datetime.now().isoformat()}")

    try:
        from src.services.arima_service import get_arima_service

        service = get_arima_service()
        result = service.run_batch()

        symbols_count = result['symbol'].nunique() if 'symbol' in result.columns else 0
        rows_count = len(result)

        response = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'ARIMA batch prediction completed',
                'symbols': symbols_count,
                'rows': rows_count,
                'timestamp': datetime.now().isoformat()
            })
        }
        print(f"ARIMA 배치 완료: {symbols_count} 종목, {rows_count} 행")
        return response

    except Exception as e:
        print(f"ARIMA 배치 실패: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'ARIMA batch prediction failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }
