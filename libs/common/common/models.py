from __future__ import annotations
from datetime import datetime
from datetime import timezone
import uuid
import re
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Index, JSON, TypeDecorator
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID, ARRAY

class Base(DeclarativeBase):
    pass


class StringArray(TypeDecorator):
    """Store string arrays in Postgres, JSON fallback for SQLite tests."""

    impl = ARRAY(String)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(JSON)
        return dialect.type_descriptor(ARRAY(String))

    def process_bind_param(self, value, dialect):
        return value or []

    def process_result_value(self, value, dialect):
        return value or []


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type."""

    impl = UUID
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(36))
        return dialect.type_descriptor(UUID())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        return value

class InstagramMedia(Base):
    __tablename__ = "instagram_media"

    id = Column(String, primary_key=True)
    caption = Column(Text, nullable=True)
    media_type = Column(String(20))  # IMAGE, VIDEO, CAROUSEL_ALBUM
    media_url = Column(String(500))
    timestamp = Column(DateTime, nullable=False)
    like_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    engagement_rate = Column(Float)  # Calculated by trigger
    hashtags = Column(StringArray, default=list)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_instagram_timestamp", "timestamp"),
        Index("idx_instagram_engagement", "engagement_rate"),
    )

    @classmethod
    def from_api_response(cls, data: dict) -> dict:
        """Convert Meta API response to database model"""
        return {
            "id": str(data["id"]),
            "caption": data.get("caption"),
            "media_type": data.get("media_type"),
            "media_url": data.get("media_url") or data.get("permalink"),
            "timestamp": datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")),
            "like_count": data.get("like_count", 0),
            "comments_count": data.get("comments_count", 0),
            "hashtags": extract_hashtags(data.get("caption", "")),
        }

class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id: Column[uuid.UUID] = Column(GUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(500), nullable=False)
    platform = Column(String(20), nullable=False)
    brand_voice = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="draft")  # draft, scheduled, published, failed

    scheduled_for = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_content_platform_status", "platform", "status"),
        Index("idx_content_scheduled", "scheduled_for"),
    )

def extract_hashtags(text: str) -> list[str]:
    """Extract hashtags from caption text"""
    if not text:
        return []
    return re.findall(r'#\w+', text)
