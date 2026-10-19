"""In-app notifications are restricted to current paper participants."""
from app.models.notification import NotificationType
from app.security.permissions import can_read
from app.storage.conference_store import ConferenceMemberNotFound
from app.storage.issue_store import IssueNotFound
from app.storage.submission_store import SubmissionNotFound


def visible(notification, user_id, conferences, submissions, issues):
    target = notification.related_id
    if not target:
        return None
    if notification.type == NotificationType.MEMBER_ADDED:
        try:
            conferences.get_member(target, user_id)
        except ConferenceMemberNotFound:
            return None
        return notification.model_copy(update={"body": "Your conference membership was updated", "email": None})
    try:
        if notification.type in {NotificationType.ISSUE_ASSIGNED, NotificationType.ISSUE_STATUS}:
            target = issues.get(target).submission_id
        paper = submissions.get(target)
    except (IssueNotFound, SubmissionNotFound):
        return None
    if not can_read(paper, user_id, conferences, submissions):
        return None
    from app.services import reviews
    if reviews.available(submissions) and submissions._connect().execute("SELECT 1 FROM review_private_notifications WHERE notification_id=?",(notification.notification_id,)).fetchone():
        if not reviews.can_chair(submissions,conferences,paper,user_id):
            return None
    return notification.model_copy(update={"body": "An update is available on a paper you can access", "email": None, "related_id": target})


def notify(notifications, submissions, conferences, paper, actor, kind, title):
    """Persist generic notifications in the same transaction as the event.

    Email delivery is intentionally deferred to a durable delivery service.
    """
    for member in conferences.list_members(paper.conference_id):
        if member.user_id == actor or not can_read(paper, member.user_id, conferences, submissions):
            continue
        if not submissions._connect().execute("SELECT 1 FROM users WHERE user_id=? AND is_active=1", (member.user_id,)).fetchone():
            continue
        notifications.create(member.user_id, kind, title, "A paper you participate in was updated", related_id=paper.submission_id)
