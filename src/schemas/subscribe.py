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

class ToggleNotificationRequest(BaseModel):
    """알림 설정 토글 요청"""
    enabled: bool