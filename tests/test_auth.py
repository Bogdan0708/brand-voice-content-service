from datetime import timedelta
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from common.auth import create_access_token, verify_token
from app.deps import get_meta_client


def test_valid_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token({"sub": "synthetic"}))
    assert verify_token(credentials)["sub"] == "synthetic"


@pytest.mark.parametrize("token", ["malformed", "a.b.c", create_access_token({"sub": "synthetic"}, timedelta(seconds=-10))])
def test_invalid_or_expired_token_returns_401(token):
    with pytest.raises(HTTPException) as error:
        verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert error.value.status_code == 401


def test_missing_meta_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    with pytest.raises(HTTPException) as error:
        get_meta_client()
    assert error.value.status_code == 503


@pytest.mark.parametrize("key", ["", "short", "default_secret_for_dev_only"])
def test_missing_or_weak_signing_key_rejects_requests(monkeypatch, key):
    import common.auth as auth
    monkeypatch.setattr(auth, "SECRET_KEY", key)
    with pytest.raises(HTTPException) as error:
        verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"))
    assert error.value.status_code == 503
