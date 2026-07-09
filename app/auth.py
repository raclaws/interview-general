import os
import time
import bcrypt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature
from sqlmodel import Session, select

from app.database import get_session
from app.models import AdminUser

SECRET_KEY = os.getenv("ADMIN_SESSION_SECRET", "change-me")
COOKIE_NAME = "session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

serializer = URLSafeSerializer(SECRET_KEY)

# Simple in-memory rate limiter for login
_login_attempts: dict[str, list[float]] = {}
LOGIN_WINDOW = 300  # 5 minutes
LOGIN_MAX_ATTEMPTS = 5


def check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate-limited."""
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < LOGIN_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) < LOGIN_MAX_ATTEMPTS


def record_login_attempt(ip: str):
    now = time.time()
    _login_attempts.setdefault(ip, []).append(now)


def clear_login_attempts(ip: str):
    _login_attempts.pop(ip, None)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_cookie(username: str, session_version: int = 1) -> str:
    return serializer.dumps({"username": username, "v": session_version})


def get_username_from_cookie(cookie: str) -> dict | None:
    try:
        data = serializer.loads(cookie)
        return data
    except BadSignature:
        return None


def get_current_admin(request: Request, db: Session = Depends(get_session)) -> AdminUser:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = get_username_from_cookie(cookie)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid session")
    username = data.get("username") if isinstance(data, dict) else data
    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not admin:
        raise HTTPException(status_code=401, detail="User not found")
    cookie_version = data.get("v", 1) if isinstance(data, dict) else 1
    if cookie_version != (admin.session_version or 1):
        raise HTTPException(status_code=401, detail="Session expired")
    return admin
