from pydantic import BaseModel
from typing import TypeVar, Generic, Optional

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T
    error: Optional[str] = None