"""Password hashing and JWT helpers (stateless Phase 1 auth)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from shared.config.settings import settings

JWT_TYPE_ACCESS = "access"
JWT_TYPE_REFRESH = "refresh"


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def _encode_token(
    subject: uuid.UUID,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a short-lived access JWT."""
    delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _encode_token(user_id, JWT_TYPE_ACCESS, delta)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived refresh JWT."""
    delta = timedelta(minutes=settings.jwt_refresh_token_expire_minutes)
    return _encode_token(user_id, JWT_TYPE_REFRESH, delta)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT; raise JWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def decode_access_token(token: str) -> uuid.UUID:
    """Decode access token and return user id."""
    payload = decode_token(token)
    if payload.get("type") != JWT_TYPE_ACCESS:
        raise JWTError("Invalid token type")
    return uuid.UUID(str(payload["sub"]))


def decode_refresh_token(token: str) -> uuid.UUID:
    """Decode refresh token and return user id."""
    payload = decode_token(token)
    if payload.get("type") != JWT_TYPE_REFRESH:
        raise JWTError("Invalid token type")
    return uuid.UUID(str(payload["sub"]))
