"""Password hashing helpers using bcrypt via passlib."""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt silently truncates (or errors) at 72 bytes — truncate explicitly so
# hash and verify are always consistent regardless of passlib/bcrypt version.
_BCRYPT_MAX = 72


def _truncate(plain: str) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX:
        encoded = encoded[:_BCRYPT_MAX]
    return encoded.decode("utf-8", errors="ignore")


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain*."""
    return pwd_context.hash(_truncate(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* password."""
    return pwd_context.verify(_truncate(plain), hashed)
