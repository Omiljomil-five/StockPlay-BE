import sys
import json

print("🚀 Lambda 모듈 로드 시작...")

def handler(event, context):
    print("=" * 80)
    print("🎯 Lambda Handler 호출!")
    print(f"📝 Event path: {event.get('path', 'N/A')}")
    print(f"📝 Event method: {event.get('httpMethod', 'N/A')}")
    print(f"🐍 Python: {sys.version}")
    print("=" * 80)
    
    try:
        print("📦 Mangum 로드 중...")
        from mangum import Mangum
        print("✅ Mangum 로드 완료")
        
        print("🚀 FastAPI 로드 중...")
        from src.main import app
        print("✅ FastAPI 로드 완료")
        
        print("🔧 Handler 생성 중...")
        handler_func = Mangum(app, lifespan="off")
        print("✅ Handler 생성 완료")
        
        print("🎬 요청 처리 시작...")
        response = handler_func(event, context)
        print(f"✅ 응답 코드: {response.get('statusCode')}")
        
        return response
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e), 'type': str(type(e).__name__)}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }

print("✅ Lambda 모듈 로드 완료!")
