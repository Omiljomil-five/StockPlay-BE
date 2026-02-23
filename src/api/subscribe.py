from fastapi import APIRouter, Path, HTTPException
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
    - 신규 구독 시 환영 이메일 전송
    - 이미 구독 중인 경우 안내 메시지 반환
    """
    try:
        db_service = get_dynamodb_service()
        result = db_service.subscribe(request.email)

        if result['success']:
            # 신규 구독 성공 - 환영 이메일 전송
            data = result['data']

            # 환영 이메일 전송 (실패해도 구독은 성공)
            email_sent = False
            try:
                from ..services.email_service import get_email_service
                email_service = get_email_service()
                email_sent = email_service.send_welcome_email(request.email)
            except Exception as email_error:
                print(f"⚠️ 환영 이메일 전송 실패 (구독은 성공): {email_error}")
                import traceback
                traceback.print_exc()

            response_data = SubscriptionResponse(
                email=data['email'],
                notification_enabled=bool(data['notification_enabled']),
                created_at=data['created_at'],
                updated_at=data['updated_at'],
                is_new_subscriber=True,
                email_sent=email_sent,
                message="구독이 완료되었습니다! 환영 이메일을 확인해주세요." if email_sent else "구독이 완료되었습니다! (환영 이메일 전송에 실패했습니다)"
            )
            return ApiResponse(success=True, data=response_data)
        else:
            # 이미 구독 중인 경우 - 에러가 아닌 성공으로 처리하되 메시지 다르게
            if "이미 구독" in result['message']:
                # 기존 구독 정보 조회
                existing = db_service.get_subscription(request.email)
                if existing:
                    response_data = SubscriptionResponse(
                        email=existing['email'],
                        notification_enabled=bool(existing['notification_enabled']),
                        created_at=existing['created_at'],
                        updated_at=existing['updated_at'],
                        is_new_subscriber=False,
                        message="이미 구독 중인 이메일입니다. 매일 오전 9시에 리포트를 받고 계십니다."
                    )
                    return ApiResponse(success=True, data=response_data)

            # 그 외 에러
            raise HTTPException(status_code=400, detail=result['message'])

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 구독 등록 API 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
            raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 구독 조회 API 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
            raise HTTPException(status_code=400, detail=result['message'])
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 알림 설정 API 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
            raise HTTPException(status_code=400, detail=result['message'])
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 구독 취소 API 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))