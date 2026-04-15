"""Password hashing helpers using bcrypt directly.

passlib 1.7.4 is incompatible with bcrypt >= 4.x (bcrypt removed __about__
and now raises ValueError for passwords > 72 bytes before passlib can
intercept it). We use bcrypt directly so we control truncation explicitly.
"""
import bcrypt

# bcrypt hard limit is 72 bytes of UTF-8. Truncate before hashing so
# hash() and verify() are always consistent.
_BCRYPT_MAX = 72


def _encode(plain: str) -> bytes:
    """Return UTF-8 bytes of *plain* capped at 72 bytes."""
    raw = plain.encode("utf-8")
    return raw[:_BCRYPT_MAX]


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain*."""
    return bcrypt.hashpw(_encode(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* password."""
    try:
        return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))
    except Exception:
        return False
