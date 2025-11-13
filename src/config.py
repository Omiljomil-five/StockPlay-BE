from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # API 설정
    API_PREFIX: str = "/api"
    
    # CORS 설정 - CloudFront URL 추가!
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000,https://dj4zhs98x0113.cloudfront.net"
    
    # AWS 설정
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "stockplay-reports-yjw-20251113"
    
    class Config:
        env_file = ".env"
    
    @property
    def origins_list(self) -> List[str]:
        """ALLOWED_ORIGINS 문자열을 리스트로 변환"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

settings = Settings()