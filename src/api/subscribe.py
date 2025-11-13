from fastapi import APIRouter, Path
from pydantic import EmailStr
from ..schemas.common import ApiResponse
from ..schemas.subscribe import SubscribeRequest, SubscriptionResponse, ToggleNotificationRequest
from ..services.dynamodb_service import get_dynamodb_service

router = APIRouter(prefix="/subscribe", tags=["subscribe"])

@router.post("", response_model=ApiResponse[SubscriptionResponse])
async def subscribe(request: SubscribeRequest):
    """
    이메일 구독 등록
    
    - **email**: 구독할 이메일 주소
    """
    try:
        db_service = get_dynamodb_service()
        result = db_service.subscribe(request.email)
        
        if result['success']:
            data = result['data']
            response_data = SubscriptionResponse(
                email=data['email'],
                notification_enabled=bool(data['notification_enabled']),
                created_at=data['created_at'],
                updated_at=data['updated_at']
            )
            return ApiResponse(success=True, data=response_data)
        else:
            return ApiResponse(
                success=False,
                data=None,
                error=result['message']
            )
    except Exception as e:
        print(f"❌ 구독 등록 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, data=None, error=str(e))


@router.get("/{email}", response_model=ApiResponse[SubscriptionResponse])
async def get_subscription(email: EmailStr = Path(..., description="조회할 이메일")):
    """
    구독 상태 조회
    
    - **email**: 조회할 이메일 주소
    """
    try:
        db_service = get_dynamodb_service()
        subscription = db_service.get_subscription(email)
        
        if subscription:
            response_data = SubscriptionResponse(
                email=subscription['email'],
                notification_enabled=bool(subscription['notification_enabled']),
                created_at=subscription['created_at'],
                updated_at=subscription['updated_at']
            )
            return ApiResponse(success=True, data=response_data)
        else:
            return ApiResponse(
                success=False,
                data=None,
                error="구독 정보를 찾을 수 없습니다."
            )
    except Exception as e:
        print(f"❌ 구독 조회 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, data=None, error=str(e))


@router.patch("/{email}", response_model=ApiResponse[SubscriptionResponse])
async def toggle_notification(
    email: EmailStr = Path(..., description="이메일 주소"),
    request: ToggleNotificationRequest = None
):
    """
    알림 설정 토글
    
    - **email**: 이메일 주소
    - **enabled**: 알림 활성화 여부
    """
    try:
        db_service = get_dynamodb_service()
        result = db_service.toggle_notification(email, request.enabled)
        
        if result['success']:
            data = result['data']
            response_data = SubscriptionResponse(
                email=data['email'],
                notification_enabled=bool(data['notification_enabled']),
                created_at=data['created_at'],
                updated_at=data['updated_at']
            )
            return ApiResponse(success=True, data=response_data)
        else:
            return ApiResponse(
                success=False,
                data=None,
                error=result['message']
            )
    except Exception as e:
        print(f"❌ 알림 설정 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, data=None, error=str(e))


@router.delete("/{email}", response_model=ApiResponse[dict])
async def unsubscribe(email: EmailStr = Path(..., description="삭제할 이메일")):
    """
    구독 취소
    
    - **email**: 취소할 이메일 주소
    """
    try:
        db_service = get_dynamodb_service()
        result = db_service.unsubscribe(email)
        
        if result['success']:
            return ApiResponse(
                success=True,
                data={'message': result['message']}
            )
        else:
            return ApiResponse(
                success=False,
                data=None,
                error=result['message']
            )
    except Exception as e:
        print(f"❌ 구독 취소 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, data=None, error=str(e))