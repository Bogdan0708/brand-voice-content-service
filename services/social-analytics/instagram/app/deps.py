import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import redis
import httpx

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://marketing_user:secure_password_here@localhost:5432/hospitality_marketing")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        r.close()

class MetaClient:
    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        self.account_id = account_id

    async def fetch_recent_media(self, limit: int = 50):
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(
                f"https://graph.facebook.com/v18.0/{self.account_id}/media",
                params={
                    "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                    "limit": limit
                },
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            return response.json().get("data", [])

def get_meta_client():
    token = os.getenv("META_ACCESS_TOKEN")
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    return MetaClient(token, account_id)
