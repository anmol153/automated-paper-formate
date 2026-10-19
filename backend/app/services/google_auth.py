"""Google Identity Services verification and explicit local-account connections."""
import re
import math
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

import requests
from fastapi import HTTPException
from google.auth import exceptions as google_errors
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app import auth
from app.config import get_settings
from app.models.user import UserInDB
from app.storage.database import MigrationRequired

CHALLENGE_COOKIE = "paper_google_challenge"
CHALLENGE_PATH = "/api/v1/auth/google"
CHALLENGE_SECONDS = 600


def available(store):
    try:
        return bool(store._connect().execute("SELECT 1 FROM schema_migrations WHERE version=7").fetchone())
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return False
        raise


def enabled(store):
    return bool(get_settings().google_oauth_client_id) and available(store)


def require_google(store):
    if not get_settings().google_oauth_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    if not available(store):
        raise MigrationRequired("Google sign-in requires the explicit schema-7 copy upgrade; see GOOGLE_AUTH.md")


def verify_google_token(credential, client_id):
    """The existing google-auth library verifies Google's signature/audience/time/issuer."""
    try:
        with requests.Session() as session:
            transport = GoogleRequest(session=session)
            def bounded_request(url, method="GET", body=None, headers=None, **kwargs):
                return transport(url, method=method, body=body, headers=headers, timeout=10)
            return id_token.verify_oauth2_token(credential, bounded_request, audience=client_id, clock_skew_in_seconds=30)
    except google_errors.TransportError as exc:
        raise HTTPException(status_code=503, detail="Google verification is temporarily unavailable; try again") from exc
    except (ValueError, google_errors.GoogleAuthError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Google could not verify this sign-in; try again") from exc


def validate_claims(claims, challenge):
    """Check required claims too; never identify an account from an unverified email."""
    now = int(time.time())
    if (not isinstance(claims, dict) or claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
            or claims.get("aud") != challenge["client_id"] or claims.get("azp", challenge["client_id"]) != challenge["client_id"]):
        raise HTTPException(status_code=401, detail="Google token was issued for a different application")
    for key in ("exp", "iat"):
        if isinstance(claims.get(key), bool) or not isinstance(claims.get(key), (int, float)) or not math.isfinite(claims[key]):
            raise HTTPException(status_code=401, detail="Google token is missing valid timestamps")
    if claims["exp"] <= now or claims["iat"] > now + 30 or claims["iat"] < challenge["created_at"] - 30:
        raise HTTPException(status_code=401, detail="Google sign-in has expired; try again")
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not secrets.compare_digest(auth.digest(nonce), challenge["nonce_hash"]):
        raise HTTPException(status_code=401, detail="Google sign-in challenge did not match; try again")
    subject, email = claims.get("sub"), claims.get("email")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or not subject.strip() or any(ord(c) < 32 for c in subject):
        raise HTTPException(status_code=401, detail="Google account identifier is invalid")
    if claims.get("email_verified") is not True or not isinstance(email, str) or len(email) > 320 or email.count("@") != 1:
        raise HTTPException(status_code=401, detail="A verified Google email address is required")
    local, domain = email.rsplit("@", 1)
    if not local or len(local) > 64 or any(c.isspace() or ord(c) < 32 for c in email) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", domain) or ".." in domain:
        raise HTTPException(status_code=401, detail="Google email address is invalid")
    name = claims.get("name")
    return {"subject": subject, "email": email.lower(), "name": name.strip()[:200] if isinstance(name, str) and name.strip() else email,
            "authoritative_email": domain.lower() == "gmail.com" or (isinstance(claims.get("hd"), str) and claims["hd"].lower() == domain.lower())}


def resolve_identity(store, identity, *, linking_user=None, current_actor=None):
    """Caller holds the account/session transaction. Google subject is the identity key."""
    conn = store._connect()
    row = conn.execute("SELECT user_id FROM google_identities WHERE subject=?", (identity["subject"],)).fetchone()
    if linking_user:
        user = store.get(linking_user)
        own = conn.execute("SELECT subject FROM google_identities WHERE user_id=?", (linking_user,)).fetchone()
        if (row and row[0] != linking_user) or (own and own[0] != identity["subject"]):
            raise HTTPException(status_code=409, detail="This Google account or Paper-Format account already has a different connection")
    elif row:
        user = store.get(row[0])
    else:
        if current_actor:
            raise HTTPException(status_code=409, detail="Sign out first, or connect Google from Account settings")
        # Password accounts are not automatically merged, even when Google is
        # authoritative for the email. Explicit linking proves both accounts.
        if conn.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (identity["email"],)).fetchone():
            raise HTTPException(status_code=409, detail="Sign in with your password and connect Google from Account settings, or choose another Google account")
        if not identity["authoritative_email"]:
            raise HTTPException(status_code=409, detail="For this email provider, create an email/password account first, then connect Google from Account settings")
        user = store.create(UserInDB(user_id="user_" + uuid4().hex, email=identity["email"], full_name=identity["name"],
            hashed_password=auth.get_password_hash(secrets.token_urlsafe(32))))
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    if current_actor and user.user_id != current_actor:
        raise HTTPException(status_code=409, detail="Sign out before switching accounts")
    if not row:
        conn.execute("INSERT INTO google_identities VALUES (?,?,?,?)", (identity["subject"], user.user_id, identity["email"], datetime.now(timezone.utc).isoformat()))
    return user
