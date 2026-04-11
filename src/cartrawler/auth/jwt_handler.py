"""JWT creation and verification using python-jose."""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from cartrawler.config import settings


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    subject: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived JWT access token."""
    expire = _utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": _utcnow(),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    expire = _utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": _utcnow(),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises ValueError with a human-readable message on failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    if payload.get("type") != expected_type:
        raise ValueError(f"Expected '{expected_type}' token, got '{payload.get('type')}'")

    return payload
