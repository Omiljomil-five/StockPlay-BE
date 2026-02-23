from pydantic import BaseModel, EmailStr
from typing import Optional

class SubscribeRequest(BaseModel):
    """구독 요청"""
    email: EmailStr

class SubscriptionResponse(BaseModel):
    """구독 정보 응답"""
    email: str
    notification_enabled: bool
    created_at: str
    updated_at: str
    is_new_subscriber: Optional[bool] = None  # 신규 구독자 여부
    message: Optional[str] = None  # 응답 메시지
    email_sent: Optional[bool] = None  # 환영 이메일 전송 성공 여부

class ToggleNotificationRequest(BaseModel):
    """알림 설정 토글 요청"""
    enabled: bool