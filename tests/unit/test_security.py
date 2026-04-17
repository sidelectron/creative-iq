"""Password hashing and JWT helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from shared.config.settings import settings
from shared.utils.security import (
    JWT_TYPE_ACCESS,
    JWT_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    h = hash_password("secret-password")
    assert verify_password("secret-password", h)
    assert not verify_password("wrong", h)


def test_access_token_decode_roundtrip() -> None:
    uid = uuid.uuid4()
    token = create_access_token(uid)
    assert decode_access_token(token) == uid


def test_refresh_token_decode_roundtrip() -> None:
    uid = uuid.uuid4()
    token = create_refresh_token(uid)
    assert decode_refresh_token(token) == uid


def test_access_decoder_rejects_refresh_token() -> None:
    uid = uuid.uuid4()
    token = create_refresh_token(uid)
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_token_exp_claim_present() -> None:
    uid = uuid.uuid4()
    token = create_access_token(uid)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["type"] == JWT_TYPE_ACCESS
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_type_in_payload() -> None:
    uid = uuid.uuid4()
    token = create_refresh_token(uid)
    payload = decode_token(token)
    assert payload["type"] == JWT_TYPE_REFRESH


def test_expired_access_token_rejected() -> None:
    uid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uid),
        "type": JWT_TYPE_ACCESS,
        "iat": int((now + timedelta(minutes=-10)).timestamp()),
        "exp": int((now + timedelta(minutes=-5)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(JWTError):
        decode_access_token(token)
