"""Single-use, account-bound conference membership links; never sends email."""
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.auth import digest
from app.models.conference import ConferenceRole
from app.services import intake
from app.storage.database import MigrationRequired


def now():
    return int(time.time())


def available(store):
    try:
        return bool(store._connect().execute('SELECT 1 FROM schema_migrations WHERE version=8').fetchone())
    except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc):
            return False
        raise


def require_invitations(store):
    if not available(store):
        raise MigrationRequired('Conference invitations require the explicit schema-8 copy upgrade; see PHASE9.md')


def audit(store, actor, action, invitation_id):
    store._connect().execute('INSERT INTO security_events(actor_id,action,target_id,created_at) VALUES (?,?,?,?)',
        (actor, action, invitation_id, datetime.now(timezone.utc).isoformat()))


def issuer_authorized(store, row):
    return bool(store._connect().execute(
        "SELECT 1 FROM conference_members m JOIN users u ON u.user_id=m.user_id WHERE m.conference_id=? AND m.user_id=? AND m.role='owner' AND u.is_active=1",
        (row['conference_id'], row['issued_by'])).fetchone())


def view(store, row):
    result = {key: row[key] for key in ('invitation_id', 'conference_id', 'recipient_email', 'role',
        'issued_by', 'created_at', 'expires_at', 'status', 'accepted_by', 'accepted_at', 'revoked_by', 'revoked_at')}
    if result['status'] == 'pending':
        if now() >= row['expires_at']:
            result['status'] = 'expired'
        elif not issuer_authorized(store, row):
            result['status'] = 'invalidated'
    return result


def require_open(store, conference_id):
    if intake.configuration(store, conference_id)['settings'].lifecycle_status == 'archived':
        raise HTTPException(status_code=409, detail='Archived conferences do not accept invitations')


def issue(store, conference_id, actor, payload):
    require_invitations(store)
    require_open(store, conference_id)
    conn = store._connect()
    matches = conn.execute('SELECT user_id,is_active FROM users WHERE lower(trim(email))=?', (payload.email,)).fetchall()
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail='Multiple accounts match this address. Add the intended account by its account ID instead.')
    user = matches[0] if matches else None
    if user and (not user['is_active'] or conn.execute('SELECT 1 FROM conference_members WHERE conference_id=? AND user_id=?', (conference_id, user['user_id'])).fetchone()):
        raise HTTPException(status_code=409, detail='This account is unavailable or already a member. Use member management for existing roles.')
    previous = conn.execute("SELECT * FROM conference_invitations WHERE conference_id=? AND recipient_email=? AND status='pending'", (conference_id, payload.email)).fetchone()
    if previous:
        state = view(store, previous)['status']
        if state == 'pending':
            raise HTTPException(status_code=409, detail='A pending invitation already exists. Revoke it before creating another link.')
        if state == 'expired':
            conn.execute("UPDATE conference_invitations SET status='expired' WHERE invitation_id=?", (previous['invitation_id'],))
        else:
            conn.execute("UPDATE conference_invitations SET status='revoked',revoked_by=?,revoked_at=? WHERE invitation_id=?", (actor, now(), previous['invitation_id']))
            audit(store, actor, 'invitation.revoked', previous['invitation_id'])
    token = secrets.token_urlsafe(32)
    invitation_id = 'invite-' + uuid4().hex
    created = now()
    conn.execute('INSERT INTO conference_invitations(invitation_id,conference_id,recipient_email,recipient_user_id,role,token_hash,issued_by,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?)',
        (invitation_id, conference_id, payload.email, user['user_id'] if user else None, payload.role, digest(token), actor, created, created + payload.expires_in_days * 86400))
    audit(store, actor, 'invitation.created', invitation_id)
    row = conn.execute('SELECT * FROM conference_invitations WHERE invitation_id=?', (invitation_id,)).fetchone()
    return {'invitation': view(store, row), 'token': token}


def page(store, conference_id, limit, before):
    if not available(store):
        return {'enabled': False, 'invitations': [], 'next_cursor': None}
    conn = store._connect()
    params = [conference_id]
    clause = ''
    if before:
        cursor = conn.execute('SELECT created_at,invitation_id FROM conference_invitations WHERE conference_id=? AND invitation_id=?', (conference_id, before)).fetchone()
        if not cursor:
            raise HTTPException(status_code=422, detail='Invalid invitation cursor')
        clause = ' AND (created_at<? OR (created_at=? AND invitation_id<?))'
        params.extend([cursor['created_at'], cursor['created_at'], cursor['invitation_id']])
    rows = conn.execute('SELECT * FROM conference_invitations WHERE conference_id=?' + clause + ' ORDER BY created_at DESC,invitation_id DESC LIMIT ?', (*params, limit + 1)).fetchall()
    return {'enabled': True, 'invitations': [view(store, row) for row in rows[:limit]],
            'next_cursor': rows[limit - 1]['invitation_id'] if len(rows) > limit else None}


def lookup(store, token, actor):
    require_invitations(store)
    conn = store._connect()
    row = conn.execute('SELECT * FROM conference_invitations WHERE token_hash=?', (digest(token),)).fetchone()
    account = conn.execute('SELECT email,is_active FROM users WHERE user_id=?', (actor,)).fetchone()
    if (row is None or account is None or not account['is_active'] or account['email'].strip().lower() != row['recipient_email']
            or (row['recipient_user_id'] and row['recipient_user_id'] != actor)):
        raise HTTPException(status_code=404, detail='Invitation unavailable for this account. Check the link and sign in with the invited address.')
    if not row['recipient_user_id']:
        matches = conn.execute('SELECT user_id FROM users WHERE lower(trim(email))=?', (row['recipient_email'],)).fetchall()
        if len(matches) != 1 or matches[0]['user_id'] != actor:
            raise HTTPException(status_code=404, detail='Invitation unavailable for this account. Ask a chair to confirm the intended account.')
    state = view(store, row)['status']
    if state == 'accepted':
        member = conn.execute('SELECT role FROM conference_members WHERE conference_id=? AND user_id=?', (row['conference_id'], actor)).fetchone()
        if row['accepted_by'] == actor and member:
            return row, member['role']
    elif state == 'pending':
        require_open(store, row['conference_id'])
        return row, None
    raise HTTPException(status_code=404, detail='Invitation expired, revoked, already used, or no longer available.')


def recipient_view(store, row, membership_role=None):
    member = store._connect().execute('SELECT role FROM conference_members WHERE conference_id=? AND user_id=?',
        (row['conference_id'], row['accepted_by'])).fetchone() if row['accepted_by'] else None
    return {'invitation_id': row['invitation_id'], 'conference_id': row['conference_id'],
            'conference_name': store.get(row['conference_id']).name, 'role': row['role'], 'expires_at': row['expires_at'],
            'status': row['status'], 'membership_role': membership_role or (member['role'] if member else None)}


def accept(store, token, actor):
    row, existing_role = lookup(store, token, actor)
    if row['status'] == 'accepted':
        return recipient_view(store, row, existing_role)
    if store._connect().execute('SELECT 1 FROM conference_members WHERE conference_id=? AND user_id=?', (row['conference_id'], actor)).fetchone():
        raise HTTPException(status_code=409, detail='You are already a member. Invitations cannot change existing roles; ask a chair to manage your membership.')
    store.add_member(row['conference_id'], actor, ConferenceRole(row['role']))
    store._connect().execute("UPDATE conference_invitations SET status='accepted',accepted_by=?,accepted_at=? WHERE invitation_id=? AND status='pending'", (actor, now(), row['invitation_id']))
    audit(store, actor, 'invitation.accepted', row['invitation_id'])
    updated = store._connect().execute('SELECT * FROM conference_invitations WHERE invitation_id=?', (row['invitation_id'],)).fetchone()
    return recipient_view(store, updated, row['role'])


def revoke(store, conference_id, invitation_id, actor):
    require_invitations(store)
    row = store._connect().execute('SELECT * FROM conference_invitations WHERE conference_id=? AND invitation_id=?', (conference_id, invitation_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail='Invitation not found')
    if row['status'] == 'revoked':
        return view(store, row)
    if row['status'] in {'accepted', 'expired'} or now() >= row['expires_at']:
        raise HTTPException(status_code=409, detail='This invitation is closed. Accepted memberships are managed separately.')
    store._connect().execute("UPDATE conference_invitations SET status='revoked',revoked_by=?,revoked_at=? WHERE invitation_id=?", (actor, now(), invitation_id))
    audit(store, actor, 'invitation.revoked', invitation_id)
    return view(store, store._connect().execute('SELECT * FROM conference_invitations WHERE invitation_id=?', (invitation_id,)).fetchone())
