import hashlib
import os

from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import SECRET_KEY, SESSION_MAX_AGE
from .db import SessionLocal, User

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="hq-session")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
        h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                           n=2**14, r=8, p=1)
        return h.hex() == h_hex
    except Exception:
        return False


def make_session_cookie(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def current_user(request: Request):
    token = request.cookies.get("hq_session")
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    db = SessionLocal()
    try:
        return db.get(User, data.get("uid"))
    finally:
        db.close()
