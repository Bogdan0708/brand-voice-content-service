import asyncio
import json
import pytest

from tests.conftest import FakeRedis, instagram_app, instagram_deps
from common.models import InstagramMedia
from app.main import health, ingest_media, account_metrics


def test_health_check(db_session):
    result = asyncio.run(health(db=db_session))
    assert result.service == "instagram-analytics"
    assert result.status == "ok"


@pytest.mark.usefixtures("mock_meta_api")
def test_ingest_media_upsert(db_session):
    class MockMetaClient:
        async def fetch_recent_media(self, limit: int = 50):
            return [{
                "id": "123",
                "caption": "Test post #vacation",
                "media_type": "IMAGE",
                "timestamp": "2026-01-07T10:00:00+0000",
                "like_count": 100,
                "comments_count": 10,
            }]

    mock_client = MockMetaClient()
    result = asyncio.run(ingest_media(limit=1, client=mock_client, db=db_session))
    assert result["ingested"] == 1

    record = db_session.query(InstagramMedia).filter_by(id="123").one()
    assert record.like_count == 100
    assert record.hashtags == ["#vacation"]

    # second call idempotent
    result2 = asyncio.run(ingest_media(limit=1, client=mock_client, db=db_session))
    assert result2["ingested"] == 1
    count = db_session.query(InstagramMedia).filter_by(id="123").count()
    assert count == 1


def test_account_metrics_uses_cache(db_session):
    cached = {"cached": True}
    fake_cache = FakeRedis()
    fake_cache.setex("instagram:account:last_7_days", 3600, json.dumps(cached))

    result = asyncio.run(
        account_metrics(
            date_range="last_7_days",
            client=None,
            redis=fake_cache,
        )
    )
    assert result == cached
