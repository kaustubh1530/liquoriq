"""
utils/security.py — Password hashing and JWT token logic

Two responsibilities:
  1. Passwords  — bcrypt hashing via passlib (never store plain text)
  2. JWT tokens — create and verify tokens via python-jose

How JWT works in LiquorIQ:
  - User logs in → we verify password → we create a signed JWT token
  - Client stores the token and sends it in every request header:
      Authorization: Bearer <token>
  - Our get_current_user dependency decodes the token → fetches the user
  - If token is expired or tampered with → 401 Unauthorized
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Log a fingerprint (NOT the key itself) at import so we can verify every
# process is using the same SECRET_KEY. If two log lines ever show different
# fingerprints, two processes are running with different configs.
logger.warning(
    "JWT config loaded: alg=%s key_fp=%s",
    settings.algorithm,
    hashlib.sha256(settings.secret_key.encode()).hexdigest()[:10],
)

# ─── Password hashing ─────────────────────────────────────────────────────────
# bcrypt is the industry standard — it's intentionally slow to resist brute force.
# deprecated="auto" automatically upgrades old hashes on next login.

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password. Call this on registration."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against a stored hash. Call this on login."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT tokens ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT token.

    Args:
        data: payload to encode (we put {"sub": user_id} in it)
        expires_delta: how long until the token expires

    Returns:
        A signed JWT string the client stores and sends back on each request.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Returns the payload dict if valid, None if expired or tampered.
    The route dependency (get_current_user) handles raising 401.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        # Log WHY validation failed (expired vs bad signature vs malformed).
        # Without this, every failure is an indistinguishable 401.
        logger.warning("JWT decode failed: %s: %s", type(e).__name__, e)
        return None