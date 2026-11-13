from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    # Milliseconds, so a sign-in right after a password change is not mistaken for an older one.
    return jwt.encode({"exp": expire, "sub": str(subject), "iat_ms": int(now.timestamp() * 1000)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def token_is_current(token: str, password_changed_at: datetime | None) -> bool:
    """False for a sign-in made before the account's password last changed."""
    if password_changed_at is None:
        return True
    try:
        issued = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]).get("iat_ms")
    except JWTError:
        return False
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    return issued is not None and issued >= int(password_changed_at.timestamp() * 1000)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
