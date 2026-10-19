"""Single-use browser-bound Google sign-in; tokens never enter browser storage."""
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import auth
from app.config import get_settings
from app.models.user import UserPublic
from app.services import google_auth as google
from app.storage.database import transaction

router = APIRouter(prefix="/api/v1/auth/google", tags=["Google sign-in"])


class LinkChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode()) > 72:
            raise ValueError("Password exceeds 72 UTF-8 bytes")
        return value


class CompleteGoogle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(min_length=32, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    credential: str = Field(min_length=1, max_length=16384)


@router.get("/config")
def config():
    settings = get_settings()
    enabled = bool(settings.google_oauth_client_id) and google.available(auth.get_user_store())
    return {"enabled": enabled, "client_id": settings.google_oauth_client_id if enabled else None}


def new_challenge(request, response, store, *, actor=None):
    challenge_id, nonce, browser = (secrets.token_urlsafe(32) for _ in range(3))
    now = int(time.time())
    with transaction(store):
        conn = store._connect()
        conn.execute("DELETE FROM google_login_challenges WHERE expires_at<=? OR browser_hash=?", (now, auth.digest(request.cookies.get(google.CHALLENGE_COOKIE, ""))))
        conn.execute("INSERT INTO google_login_challenges VALUES (?,?,?,?,?,?,?,?,?)", (
            auth.digest(challenge_id), auth.digest(nonce), auth.digest(browser), get_settings().google_oauth_client_id,
            "link" if actor else "login", actor, request.state.session_hash if actor else None, now, now + google.CHALLENGE_SECONDS))
    response.set_cookie(google.CHALLENGE_COOKIE, browser, max_age=google.CHALLENGE_SECONDS, httponly=True,
                        secure=get_settings().cookie_secure, samesite="lax", path=google.CHALLENGE_PATH)
    return {"challenge_id": challenge_id, "nonce": nonce, "expires_in": google.CHALLENGE_SECONDS,
            "client_id": get_settings().google_oauth_client_id}


@router.post("/challenge")
def login_challenge(request: Request, response: Response):
    auth.check_origin(request)
    store = auth.get_user_store()
    google.require_google(store)
    auth.limit_requests(request, "google-challenge", 20, 900)
    return new_challenge(request, response, store)


@router.post("/link/challenge")
def link_challenge(body: LinkChallenge, request: Request, response: Response, actor: str = Depends(auth.get_current_user_id)):
    auth.check_origin(request)
    store = auth.get_user_store()
    google.require_google(store)
    auth.limit_requests(request, "google-link", 10, 900, user_id=actor)
    user = store.get(actor)
    if not auth.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Confirm your current password to connect Google")
    return new_challenge(request, response, store, actor=actor)


def consume_challenge(request, store, challenge_id):
    now = int(time.time())
    browser = request.cookies.get(google.CHALLENGE_COOKIE)
    if not browser:
        raise HTTPException(status_code=400, detail="Google sign-in needs cookies; start again")
    with transaction(store):
        conn = store._connect()
        row = conn.execute("SELECT * FROM google_login_challenges WHERE challenge_hash=?", (auth.digest(challenge_id),)).fetchone()
        if not row or row["expires_at"] <= now or row["client_id"] != get_settings().google_oauth_client_id or not secrets.compare_digest(row["browser_hash"], auth.digest(browser)):
            raise HTTPException(status_code=400, detail="Google sign-in has expired or was already used; start again")
        result = dict(row)
        # Consume before certificate/network verification. Failed attempts need a
        # fresh challenge; simultaneous/replayed requests cannot mint two sessions.
        conn.execute("DELETE FROM google_login_challenges WHERE challenge_hash=?", (row["challenge_hash"],))
    return result


@router.post("/complete", response_model=UserPublic)
def complete(body: CompleteGoogle, request: Request, response: Response):
    auth.check_origin(request)
    store = auth.get_user_store()
    google.require_google(store)
    auth.limit_requests(request, "google-complete", 20, 900)
    challenge = consume_challenge(request, store, body.challenge_id)
    response.delete_cookie(google.CHALLENGE_COOKIE, path=google.CHALLENGE_PATH, secure=get_settings().cookie_secure, httponly=True, samesite="lax")
    identity = google.validate_claims(google.verify_google_token(body.credential, challenge["client_id"]), challenge)
    with transaction(store):
        if challenge["expires_at"] <= int(time.time()):
            raise HTTPException(status_code=400, detail="Google sign-in expired during verification; try again")
        actor = auth.get_optional_user_id(request)
        if challenge["intent"] == "link" and (actor != challenge["user_id"] or request.state.session_hash != challenge["session_hash"]):
            raise HTTPException(status_code=401, detail="Your session changed; sign in and connect Google again")
        user = google.resolve_identity(store, identity, linking_user=challenge["user_id"], current_actor=actor)
        if actor:
            store._connect().execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=?", (int(time.time()), request.state.session_hash))
        # Atomic account/connection, session and audit writes; no Google tokens persist.
        auth.issue_session(user.user_id, response)
        store._connect().execute("INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES (?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))", (
            user.user_id, "auth.google_connected" if challenge["intent"] == "link" else "auth.google_signed_in", user.user_id))
    return UserPublic.model_validate(user.model_dump())


@router.get("/connection")
def connection(actor: str = Depends(auth.get_current_user_id)):
    store = auth.get_user_store()
    ready = google.available(store)
    row = store._connect().execute("SELECT email_at_link,linked_at FROM google_identities WHERE user_id=?", (actor,)).fetchone() if ready else None
    return {"enabled": bool(get_settings().google_oauth_client_id) and ready, "connected": bool(row),
            "email_at_link": row[0] if row else None, "linked_at": row[1] if row else None}
