from importlib import import_module, util
from pathlib import Path
import sys
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "libs" / "common"))
sys.path.append(str(BASE_DIR / "services" / "social-analytics" / "instagram"))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
os.environ.setdefault("JWT_SECRET_KEY", "synthetic-test-jwt-secret-at-least-32-bytes")
os.environ.setdefault("ENABLE_METRICS", "0")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")

from common.auth import create_access_token  # noqa: E402
from common.models import Base  # noqa: E402

# Import Instagram service as package (uses relative imports)
instagram_main = import_module("app.main")
instagram_deps = import_module("app.deps")
instagram_app = instagram_main.app

# Load generator service without clobbering the instagram app module name
generator_main_path = BASE_DIR / "services" / "content-automation" / "generator" / "app" / "main.py"
generator_spec = util.spec_from_file_location("generator_service", generator_main_path)
generator_module = util.module_from_spec(generator_spec)
assert generator_spec and generator_spec.loader
generator_spec.loader.exec_module(generator_module)
generator_app = generator_module.app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def close(self):
        return None


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def instagram_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        redis = FakeRedis()
        try:
            yield redis
        finally:
            redis.close()

    instagram_app.dependency_overrides[instagram_deps.get_db] = override_get_db
    instagram_app.dependency_overrides[instagram_deps.get_redis] = override_get_redis
    instagram_deps.engine = db_session.get_bind()

    with TestClient(instagram_app) as client:
        yield client

    instagram_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def generator_client():
    generator_app.dependency_overrides[generator_module.verify_token] = lambda: {"sub": "test-user"}
    with TestClient(generator_app) as client:
        yield client
    generator_app.dependency_overrides.clear()


@pytest.fixture
def auth_header():
    token = create_access_token({"sub": "test-user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_meta_api(monkeypatch):
    """Mock Meta Graph API responses"""

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

    def override_get_meta_client():
        yield MockMetaClient()

    instagram_app.dependency_overrides[instagram_deps.get_meta_client] = override_get_meta_client

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

    async def mock_get(*args, **kwargs):
        return MockResponse({"data": []})

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    yield

    instagram_app.dependency_overrides.pop(instagram_deps.get_meta_client, None)
