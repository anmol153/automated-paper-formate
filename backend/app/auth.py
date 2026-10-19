from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings
from .models.user import UserCreate, UserInDB, UserPublic
from .storage import get_user_store
from .storage.database import require_security_schema
from .storage.user_store import UserNotFound

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
SESSION_COOKIE = "paper_session"
CSRF_COOKIE = "paper_csrf"
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({**data, "iat": now, "exp": now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))},
                      get_settings().secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM],
                          options={"require_exp": True, "require_sub": True})
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(email: str, password: str) -> UserInDB | None:
    user = get_user_store().get_by_email(email)
    # Also hash a dummy value for unknown accounts to reduce timing differences.
    if user is None:
        pwd_context.hash("unknown-account-padding")
        return None
    return user if user.is_active and verify_password(password, user.hashed_password) else None


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    same_origin = str(request.base_url).rstrip("/")
    if origin and origin not in {same_origin, *get_settings().cors_origins}:
        raise HTTPException(status_code=403, detail="Request origin is not allowed")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site authentication is not allowed")


def limit_requests(request: Request, category: str, limit: int, seconds: int, *, user_id: str = "") -> None:
    conn = get_user_store()._connect()
    require_security_schema(conn)
    now = int(time.time())
    address = request.client.host if request.client else "unknown"
    bucket = digest(f"{category}:{user_id or address}")
    row = conn.execute(
        "INSERT INTO request_limits AS current_limit(bucket, attempts, resets_at) VALUES (?,1,?) "
        "ON CONFLICT(bucket) DO UPDATE SET "
        "attempts=CASE WHEN current_limit.resets_at<=? THEN 1 ELSE current_limit.attempts+1 END, "
        "resets_at=CASE WHEN current_limit.resets_at<=? THEN excluded.resets_at ELSE current_limit.resets_at END "
        "RETURNING attempts, resets_at", (bucket, now + seconds, now, now),
    ).fetchone()
    if row[0] > limit:
        raise HTTPException(status_code=429, detail="Too many requests; try again later",
                            headers={"Retry-After": str(max(1, row[1] - now))})
    # Bound retained rate-limit records without keeping raw IP addresses.
    conn.execute("DELETE FROM request_limits WHERE resets_at < ?", (now - 3600,))


def _session_payload(request: Request) -> dict | None:
    authorization = request.headers.get("authorization", "")
    cookie_mode = not authorization
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid authorization header")
    else:
        token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    payload = decode_access_token(token)
    conn = get_user_store()._connect()
    require_security_schema(conn)
    session = conn.execute("SELECT user_id, csrf_hash FROM auth_sessions WHERE token_hash=? "
                           "AND revoked_at IS NULL AND expires_at>?", (digest(token), int(time.time()))).fetchone()
    if session is None or session[0] != payload.get("sub"):
        raise HTTPException(status_code=401, detail="Session has expired or was revoked")
    try:
        user = get_user_store().get(session[0])
    except UserNotFound as exc:
        raise HTTPException(status_code=401, detail="Account is unavailable") from exc
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    if cookie_mode and request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not secrets.compare_digest(digest(supplied), session[1]):
            raise HTTPException(status_code=403, detail="CSRF token is missing or invalid")
    request.state.session_hash = digest(token)
    return payload


def get_optional_user_id(request: Request) -> str | None:
    payload = _session_payload(request)
    return payload["sub"] if payload else None


def get_current_user_id(request: Request) -> str:
    user_id = get_optional_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    return user_id


def get_current_user_payload(request: Request) -> dict:
    return {"sub": get_current_user_id(request)}


@router.post("/register", response_model=UserPublic)
def register(user_create: UserCreate, request: Request):
    check_origin(request)
    limit_requests(request, "register", 10, 900)
    store = get_user_store()
    if store.get_by_email(user_create.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserInDB.from_create(f"user_{uuid4().hex}", user_create)
    try:
        store.create(user)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Email already registered") from exc
    return UserPublic.model_validate(user.model_dump())


@router.post("/login")
def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    check_origin(request)
    limit_requests(request, "login", 10, 900)
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return issue_session(user.user_id, response)


def issue_session(user_id: str, response: Response):
    """Use the same revocable cookie/CSRF session for password and Google login."""
    token = create_access_token({"sub": user_id, "jti": uuid4().hex})
    csrf = secrets.token_urlsafe(32)
    get_user_store()._connect().execute(
        "INSERT INTO auth_sessions(token_hash,user_id,csrf_hash,expires_at) VALUES (?,?,?,?)",
        (digest(token), user_id, digest(csrf), int(time.time()) + ACCESS_TOKEN_EXPIRE_MINUTES * 60),
    )
    settings = get_settings()
    for name, value, http_only in [(SESSION_COOKIE, token, True), (CSRF_COOKIE, csrf, False)]:
        response.set_cookie(name, value, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                            httponly=http_only, secure=settings.cookie_secure, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    # Kept for non-browser API clients. The browser uses only HttpOnly cookies.
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
def me(response: Response, user_id: str = Depends(get_current_user_id)):
    response.headers["Cache-Control"] = "no-store"
    return UserPublic.model_validate(get_user_store().get(user_id).model_dump())


@router.post("/logout")
def logout(request: Request, response: Response, user_id: str = Depends(get_current_user_id)):
    get_user_store()._connect().execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND user_id=?",
                                      (int(time.time()), request.state.session_hash, user_id))
    for name in [SESSION_COOKIE, CSRF_COOKIE]:
        response.delete_cookie(name, path="/", secure=get_settings().cookie_secure, httponly=name == SESSION_COOKIE, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Signed out"}
