import os
import bcrypt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature
from sqlmodel import Session, select

from app.database import get_session
from app.models import AdminUser

SECRET_KEY = os.getenv("ADMIN_SESSION_SECRET", "change-me")
COOKIE_NAME = "session"

serializer = URLSafeSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_cookie(username: str) -> str:
    return serializer.dumps({"username": username})


def get_username_from_cookie(cookie: str) -> str | None:
    try:
        data = serializer.loads(cookie)
        return data.get("username")
    except BadSignature:
        return None


def get_current_admin(request: Request, db: Session = Depends(get_session)) -> AdminUser:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = get_username_from_cookie(cookie)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid session")
    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not admin:
        raise HTTPException(status_code=401, detail="User not found")
    return admin
