"""Invitation capabilities, explicit acceptance, races and copy-only activation."""
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.models.user import UserInDB
from app.services import invitations
from app.storage import migrate

from .test_phase1_security import password_hash, world  # noqa: F401


def url(w):
    return f'/api/v1/conferences/{w.conf.conference_id}/invitations'


def issue(w, **overrides):
    result = w.client('chair').post(url(w), json={'email': 'outsider@example.org', 'role': 'reviewer', **overrides})
    assert result.status_code == 201, result.text
    return result.json()


def use(w, token, actor='outsider', action='accept'):
    return w.client(actor).post('/api/v1/invitations/' + action, json={'token': token})


def test_link_is_hashed_private_and_inspection_does_not_join(world):
    w = world
    created = issue(w, email='  OUTSIDER@EXAMPLE.ORG ')
    token = created['token']
    assert len(token) == 43 and created['invitation']['recipient_email'] == 'outsider@example.org'
    row = w.conferences._connect().execute('SELECT * FROM conference_invitations').fetchone()
    assert row['token_hash'] == auth.digest(token) and row['token_hash'] != token
    assert row['recipient_user_id'] == 'outsider'
    history = w.client('chair').get(url(w))
    assert history.status_code == 200 and history.json()['enabled']
    assert token not in history.text and 'token_hash' not in history.text
    inspected = use(w, token, action='inspect')
    assert inspected.status_code == 200 and inspected.json()['conference_name'] == w.conf.name
    assert not w.conferences.user_has_role(w.conf.conference_id, 'outsider', 'author')
    assert token not in json.dumps([tuple(row) for row in w.conferences._connect().execute('SELECT * FROM security_events')])
    assert history.headers['cache-control'] == 'private, no-store'


@pytest.mark.parametrize('role', ['author', 'reviewer'])
def test_accept_is_explicit_single_use_and_does_not_restore_removed_membership(world, role):
    w = world
    token = issue(w, role=role)['token']
    result = use(w, token)
    assert result.status_code == 200 and result.json()['membership_role'] == role
    assert w.conferences.get_member(w.conf.conference_id, 'outsider').role.value == role
    assert use(w, token).status_code == 200
    assert w.conferences._connect().execute("SELECT count(*) FROM security_events WHERE action='invitation.accepted'").fetchone()[0] == 1
    assert w.client('chair').delete(f'/api/v1/conferences/{w.conf.conference_id}/members/outsider').status_code == 204
    assert use(w, token).status_code == 404
    assert w.conferences._connect().execute('SELECT 1 FROM conference_members WHERE user_id=? AND conference_id=?', ('outsider', w.conf.conference_id)).fetchone() is None


def test_wrong_account_and_anonymous_cannot_inspect_or_accept(world):
    token = issue(world)['token']
    for action in ['inspect', 'accept']:
        assert use(world, token, actor='author', action=action).status_code == 404
        assert use(world, 'x' * 43, action=action).status_code == 404
        with TestClient(world.app) as anonymous:
            assert anonymous.post('/api/v1/invitations/' + action, json={'token': token}).status_code == 401
    assert use(world, token).status_code == 200


def test_new_account_can_sign_up_before_acceptance(world):
    w = world
    created = issue(w, email='newparticipant@example.org', role='author')
    client = TestClient(w.app, base_url='https://testserver')
    try:
        registered = client.post('/api/v1/auth/register', json={'email': 'newparticipant@example.org', 'full_name': 'New participant', 'password': 'safe-password123'})
        assert registered.status_code == 200
        login = client.post('/api/v1/auth/login', data={'username': 'newparticipant@example.org', 'password': 'safe-password123'})
        assert login.status_code == 200
        headers = {'X-CSRF-Token': client.cookies.get(auth.CSRF_COOKIE), 'Origin': 'http://localhost:5173', 'Sec-Fetch-Site': 'same-origin'}
        result = client.post('/api/v1/invitations/accept', json={'token': created['token']}, headers=headers)
        assert result.status_code == 200
        assert w.conferences.get_member(w.conf.conference_id, registered.json()['user_id']).role.value == 'author'
    finally:
        client.close()


def test_only_chairs_create_list_or_revoke_and_scope_is_enforced(world):
    w = world
    created = issue(w)
    for actor in ['author', 'reviewer', 'outsider']:
        client = w.client(actor)
        assert client.get(url(w)).status_code == 403
        assert client.post(url(w), json={'email': 'new@example.org'}).status_code == 403
        assert client.delete(url(w) + '/' + created['invitation']['invitation_id']).status_code == 403
    other = w.client('chair').post('/api/v1/conferences/', json={'name': 'Another'}).json()
    assert w.client('chair').delete(f"/api/v1/conferences/{other['conference_id']}/invitations/" + created['invitation']['invitation_id']).status_code == 404


def test_revocation_and_expiry_are_final_and_pending_links_can_be_reissued(world, monkeypatch):
    w = world
    created = issue(w)
    revoked = w.client('chair').delete(url(w) + '/' + created['invitation']['invitation_id'])
    assert revoked.status_code == 200 and revoked.json()['status'] == 'revoked'
    assert w.client('chair').delete(url(w) + '/' + created['invitation']['invitation_id']).json() == revoked.json()
    assert use(w, created['token']).status_code == 404
    second = issue(w, expires_in_days=1)
    monkeypatch.setattr(invitations, 'now', lambda: second['invitation']['expires_at'])
    assert use(w, second['token']).status_code == 404
    assert any(row['status'] == 'expired' for row in w.client('chair').get(url(w)).json()['invitations'])
    third = issue(w)
    assert third['token'] != second['token']
    assert use(w, second['token']).status_code == 404
    assert use(w, third['token']).status_code == 200


def test_duplicates_and_existing_roles_never_get_overwritten(world):
    w = world
    created = issue(w)
    assert w.client('chair').post(url(w), json={'email': 'outsider@example.org', 'role': 'author'}).status_code == 409
    assert w.client('chair').post(url(w), json={'email': 'author@example.org'}).status_code == 409
    assert w.client('chair').post(f'/api/v1/conferences/{w.conf.conference_id}/members', json={'user_id': 'outsider', 'role': 'owner'}).status_code == 201
    assert use(w, created['token']).status_code == 409
    assert w.conferences.get_member(w.conf.conference_id, 'outsider').role.value == 'owner'


@pytest.mark.parametrize('change', ['removed_issuer', 'inactive_issuer', 'archived'])
def test_stale_authority_and_archival_block_outstanding_invites(world, change):
    w = world
    created = issue(w)
    conn = w.conferences._connect()
    if change == 'removed_issuer':
        conn.execute("UPDATE conference_members SET role='author' WHERE user_id='chair' AND conference_id=?", (w.conf.conference_id,))
    elif change == 'inactive_issuer':
        conn.execute("UPDATE users SET is_active=0 WHERE user_id='chair'")
    else:
        from app.models.intake import ConfigureConference, ConferenceSettings
        from app.services import intake
        intake.configure(w.conferences, w.conf.conference_id, ConfigureConference(expected_version=0, settings=ConferenceSettings(lifecycle_status='closed')), 'chair')
        # Existing world contains an unfinalized legacy paper; archive configuration
        # is injected for this guard test without bypassing real lifecycle tests.
        old = intake.configuration(w.conferences, w.conf.conference_id)
        conn.execute('UPDATE conference_settings SET settings_json=? WHERE conference_id=?', (old['settings'].model_copy(update={'lifecycle_status': 'archived'}).model_dump_json(), w.conf.conference_id))
    assert use(w, created['token']).status_code in {404, 409}
    assert conn.execute("SELECT 1 FROM conference_members WHERE user_id='outsider' AND conference_id=?", (w.conf.conference_id,)).fetchone() is None


@pytest.mark.parametrize('payload', [
    {'email': 'not-an-email'}, {'email': 'a@@example.org'}, {'email': 'a@bad..domain'},
    {'email': 'a@example.org', 'role': 'owner'}, {'email': 'a@example.org', 'expires_in_days': 0},
    {'email': 'a@example.org', 'expires_in_days': 31}, {'email': 'a@example.org', 'expires_in_days': True},
    {'email': 'a@example.org', 'issued_by': 'outsider'},
])
def test_invalid_terms_cannot_create_invites(world, payload):
    assert world.client('chair').post(url(world), json=payload).status_code == 422
    assert world.conferences._connect().execute('SELECT count(*) FROM conference_invitations').fetchone()[0] == 0


def test_concurrent_acceptance_is_idempotent_and_accept_revoke_race_is_atomic(world):
    w = world
    created = issue(w)
    client = w.client('outsider')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post('/api/v1/invitations/accept', json={'token': created['token']}), range(2)))
    assert [row.status_code for row in results] == [200, 200]
    assert w.conferences._connect().execute("SELECT count(*) FROM security_events WHERE action='invitation.accepted'").fetchone()[0] == 1
    w.conferences.remove_member(w.conf.conference_id, 'outsider')
    second = issue(w)
    chair = w.client('chair')
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(client.post, '/api/v1/invitations/accept', json={'token': second['token']})
        b = pool.submit(chair.delete, url(w) + '/' + second['invitation']['invitation_id'])
        accepted, revoked = a.result(), b.result()
    assert (accepted.status_code, revoked.status_code) in {(200, 409), (404, 200)}


def test_failed_audit_rolls_back_membership_and_token_consumption(world, monkeypatch):
    created = issue(world)
    def fail(*args):
        raise RuntimeError('Audit failure')
    monkeypatch.setattr(invitations, 'audit', fail)
    with TestClient(world.app, base_url='https://testserver', raise_server_exceptions=False) as client:
        client.headers['Authorization'] = world.client('outsider').headers['Authorization']
        result = client.post('/api/v1/invitations/accept', json={'token': created['token']})
        assert result.status_code == 500
    row = world.conferences._connect().execute('SELECT status FROM conference_invitations').fetchone()
    assert row[0] == 'pending'
    assert world.conferences._connect().execute("SELECT 1 FROM conference_members WHERE user_id='outsider' AND conference_id=?", (world.conf.conference_id,)).fetchone() is None


def test_cookie_csrf_origin_and_rate_limits_are_enforced(world):
    w = world
    token = issue(w)['token']
    client = w.client('outsider', cookie=True)
    assert client.post('/api/v1/invitations/accept', json={'token': token}).status_code == 403
    headers = {'X-CSRF-Token': client.cookies.get(auth.CSRF_COOKIE), 'Origin': 'https://untrusted.example'}
    assert client.post('/api/v1/invitations/accept', json={'token': token}, headers=headers).status_code == 403
    conn = w.users._connect()
    use(w, token, action='inspect')
    conn.execute('UPDATE request_limits SET attempts=120 WHERE bucket=?', (auth.digest('invitation-inspect:outsider'),))
    assert use(w, token, action='inspect').status_code == 429


def test_history_is_paginated_and_closed_invitation_terms_are_immutable(world):
    w = world
    first = issue(w)
    w.client('chair').delete(url(w) + '/' + first['invitation']['invitation_id'])
    issue(w, email='another@example.org')
    page = w.client('chair').get(url(w), params={'limit': 1}).json()
    older = w.client('chair').get(url(w), params={'limit': 1, 'before': page['next_cursor']}).json()
    assert len(page['invitations']) == len(older['invitations']) == 1
    assert page['invitations'][0]['invitation_id'] != older['invitations'][0]['invitation_id']
    assert w.client('chair').get(url(w), params={'before': 'unknown'}).status_code == 422
    conn = w.conferences._connect()
    for sql in ["UPDATE conference_invitations SET role='author'", "DELETE FROM conference_invitations", "UPDATE conference_invitations SET status='pending' WHERE status='revoked'"]:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)


def test_existing_account_binding_and_ambiguous_new_addresses_fail_closed(world):
    w = world
    created = issue(w)
    w.users.create(UserInDB(user_id='case-account', email='OUTSIDER@example.org', full_name='Other', hashed_password=w.password_hash))
    def accept_as(email, token):
        with TestClient(w.app, base_url='https://testserver') as client:
            login = client.post('/api/v1/auth/login', data={'username': email, 'password': 'password123'})
            assert login.status_code == 200
            client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
            return client.post('/api/v1/invitations/accept', json={'token': token})
    assert accept_as('OUTSIDER@example.org', created['token']).status_code == 404
    assert use(w, created['token']).status_code == 200
    assert w.client('chair').post(url(w), json={'email': 'outsider@example.org'}).status_code == 409
    fresh = issue(w, email='new-address@example.org')
    for identifier, email in [('new-one', 'new-address@example.org'), ('new-two', 'NEW-ADDRESS@example.org')]:
        w.users.create(UserInDB(user_id=identifier, email=email, full_name=identifier, hashed_password=w.password_hash))
    assert accept_as('new-address@example.org', fresh['token']).status_code == 404
    assert accept_as('NEW-ADDRESS@example.org', fresh['token']).status_code == 404


@pytest.fixture
def schema7_world(monkeypatch, request):
    all_migrations = migrate.MIGRATIONS
    monkeypatch.setattr(migrate, 'MIGRATIONS', tuple(item for item in all_migrations if item[0] <= 7))
    w = request.getfixturevalue('world')
    monkeypatch.setattr(migrate, 'MIGRATIONS', all_migrations)
    return w


def test_schema7_stays_usable_until_explicit_copy_upgrade(schema7_world):
    w = schema7_world
    assert w.client('chair').get(url(w)).json() == {'enabled': False, 'invitations': [], 'next_cursor': None}
    assert w.client('chair').post(url(w), json={'email': 'outsider@example.org'}).status_code == 503
    assert w.client('chair').get(f'/api/v1/conferences/{w.conf.conference_id}').status_code == 200
    source = w.conferences.db_path
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    target = w.tmp_path / 'schema8.db'
    migrate.upgrade_target(source, target, offline=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert w.conferences._connect().execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 7
    with sqlite3.connect(target) as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 8
        assert conn.execute('SELECT count(*) FROM conference_invitations').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM users').fetchone()[0] == 7
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
