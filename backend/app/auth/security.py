"""Security and Cryptography Module for Password Hashing and JWT Authentication."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import bcrypt
import jwt
from app.config import settings


# =============================================================================
# PASSWORD SECURITY & VALIDATION
# =============================================================================

def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password strength against security policies.

    Requirements:
    - At least 8 characters long
    - Must contain at least one letter and at least one digit or symbol
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."

    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one digit or special character."

    return True, None


from pwdlib import PasswordHash

_pwd_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash plaintext password securely using Argon2."""
    return _pwd_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored hash (supporting both Argon2 and bcrypt)."""
    if not hashed_password or not plain_password:
        return False
    try:
        if hashed_password.startswith("$argon2"):
            return _pwd_hash.verify(plain_password, hashed_password)
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# =============================================================================
# JWT AUTHENTICATION TOKENS
# =============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Contains minimal non-sensitive identity metadata (user id, email).
    Never encodes passwords, hashes, or secrets.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "access_token",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a signed JWT access token.

    Returns payload dict if valid and unexpired; returns None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None


# Backward-compatible alias
decode_access_token = verify_access_token
