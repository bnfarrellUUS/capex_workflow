from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.extensions import db
from app.models import User
from app.services.security import verify_password, hash_password

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

# Precomputed hash used only to equalize timing for unknown usernames.
_DUMMY_HASH = hash_password("timing-equalization-placeholder")


@dataclass
class AuthResult:
    ok: bool
    user: Optional[User] = None
    error: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; treat stored timestamps as UTC so
    # comparisons against an aware "now" don't raise TypeError.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def authenticate(username: str, password: str) -> AuthResult:
    uname = (username or "").strip().lower()
    user = db.session.query(User).filter_by(username=uname).one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)  # equalize timing
        return AuthResult(ok=False, error="Invalid username or password.")

    if user.locked_until is not None and _as_aware(user.locked_until) > _now():
        return AuthResult(ok=False, error="Account locked. Try again later.")

    if not user.active:
        return AuthResult(ok=False, error="Account is inactive.")

    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
        db.session.commit()
        return AuthResult(ok=False, error="Invalid username or password.")

    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return AuthResult(ok=True, user=user)
