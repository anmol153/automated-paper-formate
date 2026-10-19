"""Real signed Google ID tokens with isolated keys, certificate transport and stores."""
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from google.auth import exceptions as google_errors
from jose import jwt

from app import auth
from app.config import get_settings
from app.services import google_auth as google

from .test_phase1_security import password_hash, world  # noqa: F401

CLIENT_ID = "test-client.apps.googleusercontent.com"
BASE = "/api/v1/auth/google"


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
            key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))


@pytest.fixture
def google_world(world, monkeypatch, signing_key):
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", CLIENT_ID)
    def certificate_request(url, **kwargs):
        assert url == "https://www.googleapis.com/oauth2/v1/certs"
        assert kwargs["timeout"] == 10
        return SimpleNamespace(status=200, data=json.dumps({"test-key": signing_key[1].decode()}).encode())
    monkeypatch.setattr(google, "GoogleRequest", lambda session: certificate_request)
    yield world


def anonymous(w, **kwargs):
    return TestClient(w.app, base_url="https://testserver", **kwargs)


def challenge(client):
    response = client.post(BASE + "/challenge")
    assert response.status_code == 200, response.text
    return response.json()


def token(signing_key, flow, **changes):
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "google-subject-1", "iat": now, "exp": now + 3600,
              "nonce": flow["nonce"], "email": "researcher@gmail.com", "email_verified": True, "name": "Google Researcher", **changes}
    return jwt.encode(claims, signing_key[0], algorithm="RS256", headers={"kid": "test-key"})


def complete(client, flow, credential):
    return client.post(BASE + "/complete", json={"challenge_id": flow["challenge_id"], "credential": credential})


def csrf(client):
    client.headers["X-CSRF-Token"] = client.cookies.get(auth.CSRF_COOKIE)


def test_new_google_account_gets_revocable_cookie_session_without_memberships(google_world, signing_key):
    w = google_world
    with anonymous(w) as client:
        assert client.get(BASE + "/config").json() == {"enabled": True, "client_id": CLIENT_ID}
        flow = challenge(client)
        credential = token(signing_key, flow)
        response = complete(client, flow, credential)
        assert response.status_code == 200, response.text
        user = response.json()
        assert user["email"] == "researcher@gmail.com" and "access_token" not in response.text and "hashed_password" not in response.text
        session_cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith(auth.SESSION_COOKIE + "="))
        assert "HttpOnly" in session_cookie and "Secure" in session_cookie and "SameSite=lax" in session_cookie
        assert client.get("/api/v1/auth/me").json()["user_id"] == user["user_id"]
        assert w.users._connect().execute("SELECT count(*) FROM conference_members WHERE user_id=?", (user["user_id"],)).fetchone()[0] == 0
        assert client.get(f"/api/v1/conferences/{w.conf.conference_id}").status_code == 404
        assert client.post("/api/v1/auth/logout").status_code == 403
        csrf(client)
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
        assert complete(client, flow, credential).status_code == 400
        assert w.users._connect().execute("SELECT count(*) FROM google_login_challenges").fetchone()[0] == 0


@pytest.mark.parametrize("changes", [
    {"nonce": "wrong"}, {"iss": "https://attacker.example"}, {"aud": "other-client"}, {"azp": "other-client"},
    {"exp": 1}, {"iat": 9999999999}, {"iat": None}, {"email_verified": False}, {"email_verified": "true"},
    {"sub": None}, {"email": "bad-address"}, {"email": "x@bad domain"},
])
def test_invalid_google_claims_never_create_accounts(google_world, signing_key, changes):
    w = google_world
    with anonymous(w) as client:
        flow = challenge(client)
        response = complete(client, flow, token(signing_key, flow, **changes))
        assert response.status_code == 401, response.text
        assert w.users._connect().execute("SELECT count(*) FROM google_identities").fetchone()[0] == 0
        assert w.users._connect().execute("SELECT count(*) FROM users").fetchone()[0] == 7


def test_wrong_signature_is_rejected_by_google_library(google_world, signing_key):
    with anonymous(google_world) as client:
        flow = challenge(client)
        valid = token(signing_key, flow)
        parts = valid.split(".")
        parts[2] = "A" * len(parts[2])
        assert complete(client, flow, ".".join(parts)).status_code == 401


def test_hmac_token_cannot_substitute_for_google_rsa_signature(google_world):
    with anonymous(google_world) as client:
        flow = challenge(client)
        forged = jwt.encode({"aud": CLIENT_ID, "iss": "https://accounts.google.com", "sub": "forged", "iat": int(time.time()), "exp": int(time.time()) + 3600,
                             "email": "forged@gmail.com", "email_verified": True, "nonce": flow["nonce"]}, "attacker-secret", algorithm="HS256", headers={"kid": "test-key"})
        assert complete(client, flow, forged).status_code == 401


def test_challenges_are_browser_bound_expiring_and_single_use(google_world, signing_key):
    w = google_world
    with anonymous(w) as original, anonymous(w) as stranger:
        flow = challenge(original)
        credential = token(signing_key, flow)
        assert complete(stranger, flow, credential).status_code == 400
        # A mismatched browser cannot consume the legitimate challenge.
        stranger.cookies.set(google.CHALLENGE_COOKIE, "wrong-browser", path=google.CHALLENGE_PATH)
        assert complete(stranger, flow, credential).status_code == 400
        assert complete(original, flow, credential).status_code == 200
    with anonymous(w) as client:
        flow = challenge(client)
        w.users._connect().execute("UPDATE google_login_challenges SET expires_at=0")
        assert complete(client, flow, token(signing_key, flow)).status_code == 400


def test_new_challenge_invalidates_older_pending_browser_challenge(google_world, signing_key):
    with anonymous(google_world) as client:
        first = challenge(client)
        second = challenge(client)
        assert complete(client, first, token(signing_key, first)).status_code == 400
        assert complete(client, second, token(signing_key, second)).status_code == 200


def test_returning_subject_keeps_account_when_google_email_changes(google_world, signing_key):
    w = google_world
    with anonymous(w) as first:
        flow = challenge(first)
        user_id = complete(first, flow, token(signing_key, flow)).json()["user_id"]
    with anonymous(w) as returning:
        flow = challenge(returning)
        response = complete(returning, flow, token(signing_key, flow, email="changed@gmail.com"))
        assert response.status_code == 200 and response.json()["user_id"] == user_id
        assert response.json()["email"] == "researcher@gmail.com"
        assert returning.get(BASE + "/connection").json()["email_at_link"] == "researcher@gmail.com"
    assert w.users._connect().execute("SELECT count(*) FROM google_identities").fetchone()[0] == 1


def test_email_collision_is_not_automatically_merged(google_world, signing_key):
    w = google_world
    w.users._connect().execute("UPDATE users SET email='Researcher@Gmail.com' WHERE user_id='author'")
    with anonymous(w) as client:
        flow = challenge(client)
        response = complete(client, flow, token(signing_key, flow))
        assert response.status_code == 409 and "password" in response.json()["detail"]
    assert w.users._connect().execute("SELECT count(*) FROM google_identities").fetchone()[0] == 0


def test_non_authoritative_email_requires_explicit_link_but_workspace_can_register(google_world, signing_key):
    w = google_world
    with anonymous(w) as client:
        flow = challenge(client)
        assert complete(client, flow, token(signing_key, flow, email="researcher@example.org")).status_code == 409
        flow = challenge(client)
        assert complete(client, flow, token(signing_key, flow, email="researcher@example.org", hd="wrong.org")).status_code == 409
        flow = challenge(client)
        assert complete(client, flow, token(signing_key, flow, email="researcher@example.org", hd="example.org")).status_code == 200


def test_explicit_link_requires_password_and_csrf_and_preserves_membership(google_world, signing_key):
    w = google_world
    client = w.client("author", cookie=True)
    assert client.post(BASE + "/link/challenge", json={"password": "password123"}).status_code == 403
    csrf(client)
    assert client.post(BASE + "/link/challenge", json={"password": "wrong"}).status_code == 403
    response = client.post(BASE + "/link/challenge", json={"password": "password123"})
    assert response.status_code == 200, response.text
    flow = response.json()
    old_token = client.cookies.get(auth.SESSION_COOKIE)
    result = complete(client, flow, token(signing_key, flow, email="different@thirdparty.example"))
    assert result.status_code == 200 and result.json()["user_id"] == "author"
    assert client.cookies.get(auth.SESSION_COOKIE) != old_token
    assert w.users._connect().execute("SELECT revoked_at FROM auth_sessions WHERE token_hash=?", (auth.digest(old_token),)).fetchone()[0]
    assert client.get(BASE + "/connection").json()["connected"]
    assert w.conferences.get_member(w.conf.conference_id, "author").role.value == "author"
    with anonymous(w) as returning:
        again = challenge(returning)
        result = complete(returning, again, token(signing_key, again, email="different@thirdparty.example"))
        assert result.status_code == 200 and result.json()["user_id"] == "author"


def test_link_challenge_cannot_complete_after_session_revocation(google_world, signing_key):
    w = google_world
    client = w.client("author", cookie=True)
    csrf(client)
    flow = client.post(BASE + "/link/challenge", json={"password": "password123"}).json()
    w.users._connect().execute("UPDATE auth_sessions SET revoked_at=1")
    assert complete(client, flow, token(signing_key, flow)).status_code == 401
    assert w.users._connect().execute("SELECT count(*) FROM google_identities").fetchone()[0] == 0


def test_disabled_account_cannot_sign_in_with_linked_google_identity(google_world, signing_key):
    w = google_world
    with anonymous(w) as client:
        flow = challenge(client)
        user = complete(client, flow, token(signing_key, flow)).json()
    w.users._connect().execute("UPDATE users SET is_active=0 WHERE user_id=?", (user["user_id"],))
    with anonymous(w) as client:
        flow = challenge(client)
        assert complete(client, flow, token(signing_key, flow)).status_code == 401


def test_account_connections_cannot_be_reassigned_or_replaced(google_world, signing_key):
    w = google_world
    author = w.client("author", cookie=True)
    csrf(author)
    flow = author.post(BASE + "/link/challenge", json={"password": "password123"}).json()
    assert complete(author, flow, token(signing_key, flow)).status_code == 200
    csrf(author)
    flow = author.post(BASE + "/link/challenge", json={"password": "password123"}).json()
    assert complete(author, flow, token(signing_key, flow, sub="different-subject")).status_code == 409
    other = w.client("other", cookie=True)
    csrf(other)
    flow = other.post(BASE + "/link/challenge", json={"password": "password123"}).json()
    assert complete(other, flow, token(signing_key, flow)).status_code == 409
    for query in ("UPDATE google_identities SET user_id='other'", "DELETE FROM google_identities"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            w.users._connect().execute(query)


def test_bad_origin_and_rate_limit_reject_before_verification(google_world):
    w = google_world
    with anonymous(w) as client:
        assert client.post(BASE + "/challenge", headers={"Origin": "https://attacker.example"}).status_code == 403
        challenge(client)
        w.users._connect().execute("UPDATE request_limits SET attempts=20 WHERE bucket=?", (auth.digest("google-challenge:testclient"),))
        assert client.post(BASE + "/challenge").status_code == 429


def test_parallel_callbacks_only_issue_one_session(google_world, signing_key):
    w = google_world
    with anonymous(w) as client:
        flow = challenge(client)
        credential = token(signing_key, flow)
        cookie = client.cookies.get(google.CHALLENGE_COOKIE)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: client.post(BASE + "/complete", headers={"Cookie": f"{google.CHALLENGE_COOKIE}={cookie}"},
                json={"challenge_id": flow["challenge_id"], "credential": credential}), range(2)))
        assert sorted(r.status_code for r in results) == [200, 400]
    assert w.users._connect().execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 1


def test_account_session_writes_roll_back_together(google_world, signing_key, monkeypatch):
    w = google_world
    def fail(*args):
        raise RuntimeError("Simulated session failure")
    monkeypatch.setattr(auth, "issue_session", fail)
    with anonymous(w, raise_server_exceptions=False) as client:
        flow = challenge(client)
        assert complete(client, flow, token(signing_key, flow)).status_code == 500
    assert w.users._connect().execute("SELECT count(*) FROM google_identities").fetchone()[0] == 0
    assert w.users._connect().execute("SELECT count(*) FROM users").fetchone()[0] == 7


def test_certificate_failure_is_safe_and_retry_requires_new_challenge(google_world, signing_key, monkeypatch):
    def fail(url, **kwargs):
        raise google_errors.TransportError("private network details")
    monkeypatch.setattr(google, "GoogleRequest", lambda session: fail)
    with anonymous(google_world) as client:
        flow = challenge(client)
        response = complete(client, flow, token(signing_key, flow))
        assert response.status_code == 503 and "private network details" not in response.text
        assert complete(client, flow, token(signing_key, flow)).status_code == 400


def test_unconfigured_google_keeps_password_login_available(world):
    with anonymous(world) as client:
        assert client.get(BASE + "/config").json() == {"enabled": False, "client_id": None}
        assert client.post(BASE + "/challenge").status_code == 503
        assert client.post("/api/v1/auth/login", data={"username": "author@example.org", "password": "password123"}).status_code == 200


def test_configured_older_schema_stays_disabled_until_explicit_upgrade(monkeypatch, request):
    from app.storage import migrate
    original = migrate.MIGRATIONS
    monkeypatch.setattr(migrate, "MIGRATIONS", tuple(item for item in original if item[0] <= 6))
    w = request.getfixturevalue("world")
    monkeypatch.setattr(migrate, "MIGRATIONS", original)
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", CLIENT_ID)
    with anonymous(w) as client:
        assert client.get(BASE + "/config").json()["enabled"] is False
        assert client.post(BASE + "/challenge").status_code == 503
        assert client.post("/api/v1/auth/login", data={"username": "author@example.org", "password": "password123"}).status_code == 200
    assert w.users._connect().execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
