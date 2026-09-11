from __future__ import annotations
import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx

from common.dto import HealthResponse
from common.auth import verify_token
from common.observability import configure_logging, setup_metrics
from .deps import get_db, get_redis, get_meta_client, engine
from common.models import InstagramMedia

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate environment
    required = ["META_ACCESS_TOKEN", "DATABASE_URL", "REDIS_URL"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        # Don't crash in dev if not set, but log it
        print(f"WARNING: Missing required env vars: {missing}")

    # Startup: test database connection
    if os.getenv("SKIP_STARTUP_CHECKS") != "1":
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            print(f"WARNING: Database connection failed: {e}")

    yield

    # Shutdown: cleanup
    engine.dispose()

app = FastAPI(title="Instagram Analytics", lifespan=lifespan)
configure_logging("instagram-analytics")
setup_metrics(app, "instagram-analytics")
logger = logging.getLogger(__name__)

@app.get("/healthz", response_model=HealthResponse)
async def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(service="instagram-analytics")
    except Exception as e:
        raise HTTPException(status_code=503, detail={"error": "db_unavailable", "message": str(e)})

@app.get("/metrics/account", dependencies=[Depends(verify_token)])
async def account_metrics(
    date_range: str = "last_7_days",
    client = Depends(get_meta_client),
    redis = Depends(get_redis)
):
    # Check cache first
    cache_key = f"instagram:account:{date_range}"
    cached = redis.get(cache_key)
    if cached:
        logger.info("cache_hit", extra={"key": cache_key})
        return json.loads(cached)

    # Fetch from API with proper error handling
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(
                f"https://graph.facebook.com/v18.0/{client.account_id}/insights",
                params={"metric": "impressions,reach", "period": "day"},
                headers={"Authorization": f"Bearer {client.access_token}"}
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Meta token expired or invalid")
        elif e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        else:
            raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Meta API timeout")

    # Cache for 1 hour
    redis.setex(cache_key, 3600, json.dumps(data))
    logger.info("cache_set", extra={"key": cache_key})
    return data

@app.post("/ingest/media", dependencies=[Depends(verify_token)])
async def ingest_media(
    limit: int = 50,
    client = Depends(get_meta_client),
    db: Session = Depends(get_db)
):
    # Fetch recent media from Instagram
    items = await client.fetch_recent_media(limit=limit)

    # Upsert to database (idempotent)
    from sqlalchemy.dialects.postgresql import insert

    payloads = [InstagramMedia.from_api_response(item) for item in items]
    if payloads:
        stmt = insert(InstagramMedia).values(payloads)
        stmt = stmt.on_conflict_do_update(
            index_elements=[InstagramMedia.id],
            set_={
                "caption": stmt.excluded.caption,
                "like_count": stmt.excluded.like_count,
                "comments_count": stmt.excluded.comments_count,
                "timestamp": stmt.excluded.timestamp,
            }
        )
        try:
            db.execute(stmt)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {"ingested": len(payloads)}
