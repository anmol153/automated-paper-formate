"""Notification pagination, recipient isolation, current access and read semantics."""
import base64
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.models.notification import NotificationType
from app.models.conference import ConferenceRole
from app import auth
from .test_phase1_security import password_hash, world  # noqa: F401

FEED = '/api/v1/notifications/feed'


def notice(w, title='Paper updated', user='author', target=None, kind=NotificationType.SUBMISSION_UPDATE):
    return w.notifications.create(user, kind, title, 'Private old text', related_id=target or w.submission.submission_id)


def test_feed_requires_authentication(world):
    with TestClient(world.app) as client:
        assert client.get(FEED).status_code == 401


def test_feed_projects_private_content_and_is_recipient_scoped(world):
    w = world
    own = notice(w)
    notice(w, user='reviewer')
    # A stale conference-wide notification must not expose another paper.
    notice(w, title='Hidden', user='other')
    response = w.client('author').get(FEED)
    assert response.status_code == 200
    row, = response.json()['items']
    assert row['notification_id'] == own.notification_id
    assert row['body'] == 'An update is available on a paper you can access'
    assert row['email'] is None
    assert w.client('other').get(FEED).json() == {'items': [], 'next_cursor': None}
    assert w.client('other').get('/api/v1/notifications/count-unread').json() == {'count': 0}


def test_stable_pagination_with_timestamp_ties_and_concurrent_new_items(world):
    w = world
    items = [notice(w, title=f'Update {i}') for i in range(7)]
    w.notifications._connect().execute("UPDATE notifications SET created_at='2026-10-18T00:00:00+00:00'")
    expected = sorted([n.notification_id for n in items], reverse=True)
    client = w.client('author')
    page = client.get(FEED, params={'limit': 2}).json()
    ids = [n['notification_id'] for n in page['items']]
    fresh = notice(w, title='Arrived after first page')
    while page['next_cursor']:
        page = client.get(FEED, params={'limit': 2, 'before': page['next_cursor']}).json()
        ids.extend(n['notification_id'] for n in page['items'])
    assert ids == expected
    assert fresh.notification_id not in ids
    assert client.get(FEED).json()['items'][0]['notification_id'] == fresh.notification_id


def test_hidden_rows_do_not_consume_page_slots_or_reveal_more_history(world):
    w = world
    for i in range(105):
        notice(w, title=f'Hidden {i}', user='other')
    visible = w.notifications.create('other', NotificationType.MEMBER_ADDED, 'Membership', 'Private', related_id=w.conf.conference_id)
    page = w.client('other').get(FEED, params={'limit': 1}).json()
    assert [n['notification_id'] for n in page['items']] == [visible.notification_id]
    assert page['next_cursor'] is None


def test_unread_filter_and_count_follow_read_actions_and_repeated_read_is_idempotent(world):
    w = world
    one, two = notice(w), notice(w)
    client = w.client('author')
    path = '/api/v1/notifications/' + one.notification_id
    assert client.patch(path).status_code == 200
    first = w.notifications._connect().execute('SELECT read_at FROM notifications WHERE notification_id=?', (one.notification_id,)).fetchone()[0]
    assert client.patch(path).status_code == 200
    assert w.notifications._connect().execute('SELECT read_at FROM notifications WHERE notification_id=?', (one.notification_id,)).fetchone()[0] == first
    assert [n['notification_id'] for n in client.get(FEED, params={'unread_only': True}).json()['items']] == [two.notification_id]
    assert client.get('/api/v1/notifications/count-unread').json() == {'count': 1}
    assert client.patch('/api/v1/notifications/read-all').json() == {'marked': 1}
    assert client.patch('/api/v1/notifications/read-all').json() == {'marked': 0}


def test_revoked_reviewer_cannot_list_count_or_mark_old_notifications(world):
    w = world
    item = notice(w, user='reviewer')
    client = w.client('reviewer')
    assert len(client.get(FEED).json()['items']) == 1
    w.submissions._connect().execute('DELETE FROM review_assignments WHERE submission_id=?', (w.submission.submission_id,))
    assert client.get(FEED).json()['items'] == []
    assert client.get('/api/v1/notifications/count-unread').json() == {'count': 0}
    assert client.patch('/api/v1/notifications/' + item.notification_id).status_code == 404
    assert client.patch('/api/v1/notifications/read-all').json() == {'marked': 0}
    assert w.notifications.count_unread('reviewer') == 1


def test_mark_all_changes_only_currently_visible_recipient_rows(world):
    w = world
    hidden = notice(w, user='other')
    own = w.notifications.create('other', NotificationType.MEMBER_ADDED, 'Membership', '', related_id=w.conf.conference_id)
    untouched = notice(w)
    assert w.client('other').patch('/api/v1/notifications/read-all').json() == {'marked': 1}
    states = dict(w.notifications._connect().execute('SELECT notification_id, read FROM notifications'))
    assert states[own.notification_id] == 1
    assert states[hidden.notification_id] == states[untouched.notification_id] == 0
    assert w.client('author').patch('/api/v1/notifications/' + own.notification_id).status_code == 404


def test_mark_all_rolls_back_as_a_unit(world, monkeypatch):
    w = world
    notice(w); notice(w)
    original = w.notifications.mark_read
    calls = []
    def fail_second(*args):
        calls.append(args)
        if len(calls) == 2:
            raise sqlite3.OperationalError('Simulated failure')
        return original(*args)
    monkeypatch.setattr(w.notifications, 'mark_read', fail_second)
    with pytest.raises(sqlite3.OperationalError):
        w.client('author').patch('/api/v1/notifications/read-all')
    assert w.notifications.count_unread('author') == 2


@pytest.mark.parametrize('query', [{'limit': 0}, {'limit': 51}, {'before': 'not-base64!'},
                                 {'before': 'a' * 513}, {'before': base64.urlsafe_b64encode(b'{}').decode()}])
def test_invalid_pagination_rejected(world, query):
    assert world.client('author').get(FEED, params=query).status_code == 422


def test_cursor_cannot_be_reused_for_another_recipient_or_filter(world):
    w = world
    notice(w); notice(w)
    cursor = w.client('author').get(FEED, params={'limit': 1}).json()['next_cursor']
    assert w.client('reviewer').get(FEED, params={'before': cursor}).status_code == 422
    assert w.client('author').get(FEED, params={'before': cursor, 'unread_only': True}).status_code == 422
    # The cursor is a position, not authorization: a forged recipient-scoped
    # position still cannot reveal another user's rows.
    payload = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
    payload[1] = 'other'
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    assert w.client('other').get(FEED, params={'before': forged}).json()['items'] == []


def test_membership_notification_disappears_after_membership_removal(world):
    w = world
    w.notifications.create('other', NotificationType.MEMBER_ADDED, 'Membership', '', related_id=w.conf.conference_id)
    client = w.client('other')
    assert len(client.get(FEED).json()['items']) == 1
    w.conferences._connect().execute('DELETE FROM conference_members WHERE conference_id=? AND user_id=?', (w.conf.conference_id, 'other'))
    assert client.get(FEED).json()['items'] == []


def test_confidential_review_notifications_require_current_chair_permission(world):
    w = world
    secret = notice(w, title='Formal review submitted', user='chair')
    w.submissions._connect().execute('INSERT INTO review_private_notifications VALUES (?)', (secret.notification_id,))
    client = w.client('chair')
    assert len(client.get(FEED).json()['items']) == 1
    # Remain able to read the paper as an assigned reviewer, but lose chair access.
    w.conferences.add_member(w.conf.conference_id, 'chair', ConferenceRole.REVIEWER)
    w.submissions.assign_reviewer(w.submission.submission_id, 'chair', 'chair')
    assert client.get('/api/v1/submissions/' + w.submission.submission_id).status_code == 200
    assert client.get(FEED).json()['items'] == []
    assert client.get('/api/v1/notifications/count-unread').json() == {'count': 0}
    assert client.patch('/api/v1/notifications/' + secret.notification_id).status_code == 404


def test_cookie_read_controls_require_csrf_and_trusted_origin(world):
    w = world
    notice(w)
    client = w.client('author', cookie=True)
    assert client.patch('/api/v1/notifications/read-all').status_code == 403
    headers = {'X-CSRF-Token': client.cookies.get(auth.CSRF_COOKIE), 'Origin': 'https://untrusted.example'}
    assert client.patch('/api/v1/notifications/read-all', headers=headers).status_code == 403
    assert w.notifications.count_unread('author') == 1
