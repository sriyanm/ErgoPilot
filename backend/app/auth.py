"""Password hashing and JWT helpers for session tokens."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
# Default is dev-only; set ERGOPILOT_JWT_SECRET in any shared or production environment.
_DEFAULT_DEV_SECRET = "ergopilot-dev-secret-change-me"


def _jwt_secret() -> str:
    secret = os.environ.get("ERGOPILOT_JWT_SECRET", "").strip()
    if secret:
        return secret
    return _DEFAULT_DEV_SECRET


def hash_password(plain: str) -> str:
    """Hash with bcrypt (compatible with hashes produced by passlib in older installs)."""
    pw = plain.encode("utf-8")
    if len(pw) > 72:
        pw = pw[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw, salt).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        pw = plain.encode("utf-8")
        if len(pw) > 72:
            pw = pw[:72]
        return bcrypt.checkpw(pw, password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(*, subject_email: str, display_name: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(days=7)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject_email,
        "name": display_name,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
