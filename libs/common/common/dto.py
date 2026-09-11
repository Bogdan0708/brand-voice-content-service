from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class HealthResponse(BaseModel):
    service: str
    status: str = "ok"
    version: str = "1.0.0"

class MediaItem(BaseModel):
    id: str
    caption: Optional[str] = None
    media_type: str
    media_url: Optional[str] = None
    timestamp: datetime
    like_count: int = Field(default=0, ge=0)
    comments_count: int = Field(default=0, ge=0)
