"""Paper lifecycle, explicit collaborator grants, threaded discussion and activity."""
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.submission_routes import _load, _member
from app.auth import get_current_user_id
from app.dependencies import get_conference_store, get_submission_store
from app.models.notification import NotificationType
from app.models.submission import SubmissionStatus
from app.security.notifications import notify
from app.security.permissions import can_edit, is_assigned_reviewer, is_chair, submission_view
from app.services import workflow, reviews
from app.storage import revisions
from app.storage.database import transaction
from app.storage.notification_store import get_notification_store

router = APIRouter(prefix="/api/v1", tags=["collaboration"])


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Policy(Payload):
    formatting_gate: Literal["allow_issues", "block_errors"]


class Transition(Payload):
    target_status: SubmissionStatus
    expected_status: SubmissionStatus
    expected_revision_id: str = Field(min_length=1, max_length=100)
    reason: str = Field("", max_length=4000)


class Collaborator(Payload):
    user_id: str = Field(min_length=1, max_length=200)
    can_edit: bool = False


class NewThread(Payload):
    body: str = Field(min_length=1, max_length=20000)
    revision_id: str | None = Field(None, max_length=100)
    page_number: int | None = Field(None, ge=1, le=10000)
    visibility: Literal["participants", "chairs"] = "participants"


class NewReply(Payload):
    body: str = Field(min_length=1, max_length=20000)
    parent_comment_id: str | None = Field(None, max_length=100)


class EditComment(Payload):
    body: str = Field(min_length=1, max_length=20000)
    expected_version: int = Field(ge=1)


class Resolve(Payload):
    resolved: bool
    expected_resolved: bool


def now():
    return datetime.now(timezone.utc).isoformat()


def paper_for(submission_id, actor, conferences, store):
    paper = _load(submission_id, actor, conferences, store)
    workflow.require_workflow(store)
    return paper


def check_text(body):
    if not body.strip():
        raise HTTPException(status_code=422, detail="Comment must not be empty")


@router.get("/conferences/{conf_id}/workflow")
async def get_policy(conf_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _member(conf_id, actor, conferences)
    workflow.require_workflow(store)
    return {"formatting_gate": workflow.policy(store, conf_id), "can_configure": is_chair(conferences, conf_id, actor)}


@router.put("/conferences/{conf_id}/workflow")
async def set_policy(conf_id: str, body: Policy, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        _member(conf_id, actor, conferences)
        workflow.require_workflow(store)
        if not is_chair(conferences, conf_id, actor):
            raise HTTPException(status_code=403, detail="Conference chair permission required")
        store._connect().execute("INSERT INTO conference_workflow VALUES (?,?) ON CONFLICT(conference_id) DO UPDATE SET formatting_gate=excluded.formatting_gate", (conf_id, body.formatting_gate))
        store.audit(actor, "conference.workflow_changed", conf_id)
    return {"formatting_gate": body.formatting_gate, "can_configure": True}


@router.get("/submissions/{submission_id}/workflow")
async def get_workflow(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    from app.services import intake
    paper = paper_for(submission_id, actor, conferences, store)
    chair = reviews.can_chair(store, conferences, paper, actor)
    decision = store._connect().execute("SELECT decision_reason FROM submission_workflow WHERE submission_id=?", (submission_id,)).fetchone()
    return {**workflow.eligibility(store, paper), "status": paper.status.value,
            "submission_window": intake.window(store, paper.conference_id, requested_revision=paper.status.value == "changes_requested"),
            "review_phase_open": intake.review_phase_open(store, paper.conference_id),
            "actions": workflow.actions(store, conferences, paper, actor),
            "can_manage_collaborators": workflow.manager(paper, actor, conferences, store), "is_chair": chair,
            "decision_reason": decision[0] if decision else "",
            "assignments": [a.model_dump(mode="json") for a in store.list_assignments(submission_id)] if chair else []}


@router.post("/submissions/{submission_id}/transitions")
async def transition_submission(submission_id: str, body: Transition, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences, notifications):
        paper = paper_for(submission_id, actor, conferences, store)
        updated = workflow.transition(store, conferences, paper, actor, body.target_status.value,
                                      expected_status=body.expected_status.value, expected_revision_id=body.expected_revision_id, reason=body.reason)
        notify(notifications, store, conferences, updated, actor, NotificationType.SUBMISSION_UPDATE, "Submission status updated")
    return submission_view(updated, actor, conferences, store)


@router.delete("/submissions/{submission_id}/assignments/{assignment_id}", status_code=204)
async def revoke_assignment(submission_id: str, assignment_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper = paper_for(submission_id, actor, conferences, store)
        if not reviews.can_chair(store, conferences, paper, actor):
            raise HTTPException(status_code=403, detail="Conference chair permission required")
        row = store._connect().execute("SELECT reviewer_id,status FROM review_assignments WHERE submission_id=? AND assignment_id=?", (submission_id, assignment_id)).fetchone()
        if row is None or row["status"] == "revoked":
            raise HTTPException(status_code=404, detail="Reviewer assignment not found")
        store._connect().execute("UPDATE review_assignments SET status='revoked' WHERE assignment_id=?", (assignment_id,))
        replacement = store._connect().execute("SELECT reviewer_id FROM review_assignments WHERE submission_id=? AND status IN ('pending','accepted','completed') ORDER BY assigned_at LIMIT 1", (submission_id,)).fetchone()
        store._connect().execute("UPDATE submissions SET reviewer_id=? WHERE submission_id=?", (replacement[0] if replacement else None, submission_id))
        store.audit(actor, "reviewer.revoked", submission_id)


@router.get("/submissions/{submission_id}/collaborators")
async def get_collaborators(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper = paper_for(submission_id, actor, conferences, store)
    # Author lists are author-visible in the current single-blind workflow.
    security = store.security(submission_id)
    return {"submitter_id": security["submitter_id"] if security else None,
            "collaborators": [dict(r) for r in store._connect().execute(
                "SELECT user_id,can_edit FROM submission_collaborators WHERE submission_id=? ORDER BY user_id", (submission_id,))],
            "can_manage": workflow.manager(paper, actor, conferences, store)}


def manage(paper, actor, conferences, store):
    if not workflow.manager(paper, actor, conferences, store):
        raise HTTPException(status_code=403, detail="Only the submitting author or chair may manage collaborators")
    if paper.status.value in workflow.TERMINAL:
        raise HTTPException(status_code=409, detail="Finalized papers cannot change author access")


@router.put("/submissions/{submission_id}/collaborators")
async def add_collaborator(submission_id: str, body: Collaborator, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences, notifications):
        paper = paper_for(submission_id, actor, conferences, store)
        manage(paper, actor, conferences, store)
        security = store.security(submission_id)
        if not security or not security["submitter_id"]:
            raise HTTPException(status_code=409, detail="Reconcile legacy ownership before adding collaborators")
        eligible = store._connect().execute(
            "SELECT 1 FROM users u JOIN conference_members m ON m.user_id=u.user_id WHERE u.user_id=? AND u.is_active=1 AND m.conference_id=?",
            (body.user_id, paper.conference_id),
        ).fetchone()
        if not eligible:
            raise HTTPException(status_code=400, detail="Coauthor must have an active account and conference membership")
        if body.user_id == security["submitter_id"]:
            raise HTTPException(status_code=409, detail="The submitting author already has access")
        if store._connect().execute("SELECT 1 FROM review_assignments WHERE submission_id=? AND reviewer_id=?", (submission_id, body.user_id)).fetchone():
            raise HTTPException(status_code=409, detail="A reviewer of this paper cannot become its collaborator")
        store._connect().execute("INSERT INTO submission_collaborators VALUES (?,?,?) ON CONFLICT(submission_id,user_id) DO UPDATE SET can_edit=excluded.can_edit", (submission_id, body.user_id, int(body.can_edit)))
        store.audit(actor, "collaborator.updated", submission_id)
        notifications.create(body.user_id, NotificationType.SUBMISSION_UPDATE, "Paper access updated", "A paper is available in your conference workspace", related_id=submission_id)
    return {"user_id": body.user_id, "can_edit": body.can_edit}


@router.delete("/submissions/{submission_id}/collaborators/{user_id}", status_code=204)
async def remove_collaborator(submission_id: str, user_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper = paper_for(submission_id, actor, conferences, store)
        manage(paper, actor, conferences, store)
        changed = store._connect().execute("DELETE FROM submission_collaborators WHERE submission_id=? AND user_id=?", (submission_id, user_id)).rowcount
        if not changed:
            raise HTTPException(status_code=404, detail="Collaborator not found")
        store.audit(actor, "collaborator.removed", submission_id)


def load_thread(store, submission_id, thread_id, actor, conferences):
    paper = paper_for(submission_id, actor, conferences, store)
    thread = store._connect().execute("SELECT * FROM paper_threads WHERE submission_id=? AND thread_id=?", (submission_id, thread_id)).fetchone()
    if thread is None or (thread["visibility"] == "chairs" and not reviews.can_chair(store, conferences, paper, actor)):
        raise HTTPException(status_code=404, detail="Discussion thread not found")
    return paper, thread


def thread_view(store, conferences, paper, thread, actor):
    result = dict(thread)
    chair = reviews.can_chair(store, conferences, paper, actor)
    comments = []
    for row in store._connect().execute("SELECT * FROM paper_comments WHERE thread_id=? ORDER BY created_at,comment_id", (thread["thread_id"],)):
        value = dict(row)
        value["body"] = "" if row["deleted_at"] else row["body"]
        value["author_id"] = workflow.identity(row["author_id"], row["author_role"], actor, chair)
        value["can_edit"] = row["author_id"] == actor and not row["deleted_at"]
        value["can_delete"] = bool((row["author_id"] == actor or chair) and not row["deleted_at"])
        comments.append(value)
    result["comments"] = comments
    root_author = store._connect().execute("SELECT author_id FROM paper_comments WHERE thread_id=? ORDER BY created_at,comment_id LIMIT 1", (thread["thread_id"],)).fetchone()
    result["can_resolve"] = bool(can_edit(paper, actor, conferences, store) or (root_author and root_author[0] == actor and is_assigned_reviewer(paper, actor, conferences, store)))
    return result


def add_comment(store, paper, thread, actor, body, parent=None):
    check_text(body)
    if thread["resolved"]:
        raise HTTPException(status_code=409, detail="Reopen this thread before replying")
    if parent and not store._connect().execute("SELECT 1 FROM paper_comments WHERE thread_id=? AND comment_id=? AND deleted_at IS NULL", (thread["thread_id"], parent)).fetchone():
        raise HTTPException(status_code=404, detail="Reply target not found in this thread")
    cid = "comment-" + uuid4().hex
    store._connect().execute(
        "INSERT INTO paper_comments(comment_id,thread_id,parent_comment_id,author_id,author_role,body,created_at) VALUES (?,?,?,?,?,?,?)",
        (cid, thread["thread_id"], parent, actor, workflow.actor_role(store._connect(), paper.submission_id, actor), body, now()),
    )
    store._connect().execute("UPDATE paper_threads SET updated_at=? WHERE thread_id=?", (now(), thread["thread_id"]))
    store.audit(actor, "conversation.comment_added", paper.submission_id, visibility=thread["visibility"], revision_id=thread["revision_id"])


def notify_thread(notifications, store, conferences, paper, actor, visibility):
    # Chair-only messages remain private; their notification delivery is deferred.
    if visibility == "participants":
        notify(notifications, store, conferences, paper, actor, NotificationType.SUBMISSION_UPDATE, "New paper conversation comment")


@router.get("/submissions/{submission_id}/conversation")
async def list_threads(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper = paper_for(submission_id, actor, conferences, store)
    chair = reviews.can_chair(store, conferences, paper, actor)
    rows = store._connect().execute("SELECT * FROM paper_threads WHERE submission_id=? AND (visibility='participants' OR ?=1) ORDER BY created_at", (submission_id, int(chair))).fetchall()
    return [thread_view(store, conferences, paper, row, actor) for row in rows]


@router.post("/submissions/{submission_id}/conversation", status_code=201)
async def create_thread(submission_id: str, body: NewThread, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences, notifications):
        paper = paper_for(submission_id, actor, conferences, store)
        if body.visibility == "chairs" and not reviews.can_chair(store, conferences, paper, actor):
            raise HTTPException(status_code=403, detail="Only chairs can create confidential threads")
        if body.page_number is not None and body.revision_id is None:
            raise HTTPException(status_code=422, detail="Page comments require an explicit revision")
        if body.revision_id:
            revisions.get_revision(store, submission_id, body.revision_id)
            if body.page_number:
                run = store._connect().execute("SELECT assessment_json FROM revision_checks WHERE revision_id=? AND assessment_json IS NOT NULL ORDER BY sequence DESC LIMIT 1", (body.revision_id,)).fetchone()
                layout = (json.loads(run[0]).get("facts") or {}).get("layout", {}) if run else {}
                if layout.get("page_count_exact") and layout.get("page_count") and body.page_number > layout["page_count"]:
                    raise HTTPException(status_code=422, detail="Page is outside this document")
        tid = "conversation-" + uuid4().hex
        store._connect().execute("INSERT INTO paper_threads VALUES (?,?,?,?,?,0,?,?)", (tid, submission_id, body.revision_id, body.page_number, body.visibility, now(), now()))
        _, thread = load_thread(store, submission_id, tid, actor, conferences)
        add_comment(store, paper, thread, actor, body.body)
        notify_thread(notifications, store, conferences, paper, actor, body.visibility)
    return thread_view(store, conferences, paper, store._connect().execute("SELECT * FROM paper_threads WHERE thread_id=?", (tid,)).fetchone(), actor)


@router.post("/submissions/{submission_id}/conversation/{thread_id}/comments", status_code=201)
async def reply(submission_id: str, thread_id: str, body: NewReply, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences, notifications):
        paper, thread = load_thread(store, submission_id, thread_id, actor, conferences)
        add_comment(store, paper, thread, actor, body.body, body.parent_comment_id)
        notify_thread(notifications, store, conferences, paper, actor, thread["visibility"])
    return thread_view(store, conferences, paper, thread, actor)


def comment_for(store, thread_id, comment_id, actor, chair=False, *, deleting=False, expected_version):
    row = store._connect().execute("SELECT * FROM paper_comments WHERE thread_id=? AND comment_id=?", (thread_id, comment_id)).fetchone()
    if row is None or row["deleted_at"]:
        raise HTTPException(status_code=404, detail="Comment not found")
    if row["author_id"] != actor and not (deleting and chair):
        raise HTTPException(status_code=403, detail="Comment belongs to another participant")
    if row["version"] != expected_version:
        raise HTTPException(status_code=409, detail="Comment changed; reload before editing")
    return row


@router.patch("/submissions/{submission_id}/conversation/{thread_id}/comments/{comment_id}")
async def edit_comment(submission_id: str, thread_id: str, comment_id: str, body: EditComment, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper, thread = load_thread(store, submission_id, thread_id, actor, conferences)
        comment_for(store, thread_id, comment_id, actor, expected_version=body.expected_version)
        check_text(body.body)
        store._connect().execute("UPDATE paper_comments SET body=?,edited_at=?,version=version+1 WHERE comment_id=?", (body.body, now(), comment_id))
        store.audit(actor, "conversation.comment_edited", submission_id, visibility=thread["visibility"], revision_id=thread["revision_id"])
    return thread_view(store, conferences, paper, thread, actor)


@router.delete("/submissions/{submission_id}/conversation/{thread_id}/comments/{comment_id}", status_code=204)
async def delete_comment(submission_id: str, thread_id: str, comment_id: str, expected_version: int = Query(ge=1), store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper, thread = load_thread(store, submission_id, thread_id, actor, conferences)
        comment_for(store, thread_id, comment_id, actor, reviews.can_chair(store, conferences, paper, actor), deleting=True, expected_version=expected_version)
        store._connect().execute("UPDATE paper_comments SET deleted_at=?,version=version+1 WHERE comment_id=?", (now(), comment_id))
        store.audit(actor, "conversation.comment_deleted", submission_id, visibility=thread["visibility"], revision_id=thread["revision_id"])


@router.patch("/submissions/{submission_id}/conversation/{thread_id}")
async def resolve_thread(submission_id: str, thread_id: str, body: Resolve, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store, conferences):
        paper, thread = load_thread(store, submission_id, thread_id, actor, conferences)
        if not thread_view(store, conferences, paper, thread, actor)["can_resolve"]:
            raise HTTPException(status_code=403, detail="Thread resolution permission required")
        if bool(thread["resolved"]) != body.expected_resolved:
            raise HTTPException(status_code=409, detail="Thread state changed; reload before acting")
        store._connect().execute("UPDATE paper_threads SET resolved=?,updated_at=? WHERE thread_id=?", (int(body.resolved), now(), thread_id))
        store.audit(actor, "conversation.resolved" if body.resolved else "conversation.reopened", submission_id, visibility=thread["visibility"], revision_id=thread["revision_id"])
    return {"resolved": body.resolved}


@router.get("/submissions/{submission_id}/activity")
async def get_activity(submission_id: str, before: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=100), store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper = paper_for(submission_id, actor, conferences, store)
    chair = reviews.can_chair(store, conferences, paper, actor)
    rows = store._connect().execute(
        "SELECT * FROM paper_events WHERE submission_id=? AND (visibility='participants' OR ?=1) AND (? IS NULL OR event_id<?) ORDER BY event_id DESC LIMIT ?",
        (submission_id, int(chair), before, before, limit+1),
    ).fetchall()
    events = []
    for row in rows[:limit]:
        value = dict(row)
        value["actor_id"] = workflow.identity(row["actor_id"], row["actor_role"], actor, chair)
        value["details"] = json.loads(value.pop("details_json"))
        events.append(value)
    return {"events": events, "next_before": events[-1]["event_id"] if len(rows)>limit else None}
