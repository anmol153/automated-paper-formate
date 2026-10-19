"""Submission-scoped issue access and atomic mutations."""
from app.auth import get_current_user_id
from app.dependencies import get_conference_store, get_submission_store
from app.models.issue import Issue, IssueComment, IssueStatus
from app.security.permissions import (
    can_edit,
    can_read,
    is_assigned_reviewer,
    paper_chair,
    require_read,
)
from app.storage.conference_store import ConferenceStore
from app.storage.database import transaction
from app.storage.issue_store import IssueNotFound, IssueStore, get_issue_store
from app.storage.submission_store import SubmissionNotFound, SubmissionStore
from fastapi import APIRouter, Body, Depends, HTTPException

router = APIRouter(prefix="/api/v1", tags=["issues"])


def _paper(submission_id, user_id, conferences, submissions):
    try:
        paper = submissions.get(submission_id)
    except SubmissionNotFound as exc:
        raise HTTPException(status_code=404, detail="Issue not found") from exc
    require_read(paper, user_id, conferences, submissions)
    return paper


def _issue(issue_id, user_id, issues, conferences, submissions):
    try:
        issue = issues.get(issue_id)
    except IssueNotFound as exc:
        raise HTTPException(status_code=404, detail="Issue not found") from exc
    return issue, _paper(issue.submission_id, user_id, conferences, submissions)


def _view(issue, paper, user_id, conferences, submissions):
    conn = submissions._connect()
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version=3").fetchone():
        origin = conn.execute(
            "SELECT c.revision_id,c.run_id FROM issue_findings f JOIN revision_checks c ON c.run_id=f.run_id WHERE f.issue_id=?",
            (issue.issue_id,),
        ).fetchone()
        if origin:
            issue = issue.model_copy(update={"revision_id": origin["revision_id"], "check_run_id": origin["run_id"]})
    if paper_chair(paper, user_id, conferences, submissions):
        return issue
    return issue.model_copy(update={
        "assignee_id": issue.assignee_id if issue.assignee_id == user_id else None,
        "resolved_by": issue.resolved_by if issue.resolved_by == user_id else None,
    })


@router.get("/submissions/{submission_id}/issues", response_model=list[Issue])
async def list_issues_for_submission(
    submission_id: str, submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    issue_store: IssueStore = Depends(get_issue_store), current_user_id: str = Depends(get_current_user_id),
):
    paper = _paper(submission_id, current_user_id, conference_store, submission_store)
    return [_view(issue, paper, current_user_id, conference_store, submission_store) for issue in issue_store.list_by_submission(submission_id)]


@router.get("/issues/{issue_id}", response_model=Issue)
async def get_issue(
    issue_id: str, submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    issue_store: IssueStore = Depends(get_issue_store), current_user_id: str = Depends(get_current_user_id),
):
    issue, paper = _issue(issue_id, current_user_id, issue_store, conference_store, submission_store)
    return _view(issue, paper, current_user_id, conference_store, submission_store)


@router.patch("/issues/{issue_id}", response_model=Issue)
async def update_issue(
    issue_id: str, status: IssueStatus | None = Body(None), assignee_id: str | None = Body(None),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    issue_store: IssueStore = Depends(get_issue_store), current_user_id: str = Depends(get_current_user_id),
):
    with transaction(submission_store, conference_store, issue_store):
        issue, paper = _issue(issue_id, current_user_id, issue_store, conference_store, submission_store)
        if status is not None and not (can_edit(paper, current_user_id, conference_store, submission_store)
                                      or is_assigned_reviewer(paper, current_user_id, conference_store, submission_store)):
            raise HTTPException(status_code=403, detail="Issue editing permission required")
        if assignee_id is not None:
            if not paper_chair(paper, current_user_id, conference_store, submission_store):
                raise HTTPException(status_code=403, detail="Only chairs can assign issues")
            if not can_read(paper, assignee_id, conference_store, submission_store):
                raise HTTPException(status_code=400, detail="Assignee cannot access this paper")
            user = submission_store._connect().execute("SELECT is_active FROM users WHERE user_id=?", (assignee_id,)).fetchone()
            if not user or not user[0]:
                raise HTTPException(status_code=400, detail="Assignee account is unavailable")
        if status is not None:
            issue = issue_store.update_status(issue_id, status, resolved_by=current_user_id)
        if assignee_id is not None:
            issue = issue_store.assign(issue_id, assignee_id)
        submission_store.audit(current_user_id, "issue.updated", issue_id)
    return _view(issue, paper, current_user_id, conference_store, submission_store)


@router.post("/issues/{issue_id}/comments", status_code=201, response_model=IssueComment)
async def add_issue_comment(
    issue_id: str, text: str = Body(..., embed=True, min_length=1, max_length=20000),
    submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    issue_store: IssueStore = Depends(get_issue_store), current_user_id: str = Depends(get_current_user_id),
):
    with transaction(submission_store, conference_store, issue_store):
        _issue(issue_id, current_user_id, issue_store, conference_store, submission_store)
        comment = issue_store.add_comment(issue_id, current_user_id, text)
        submission_store.audit(current_user_id, "issue.comment_added", issue_id)
    return comment


@router.get("/issues/{issue_id}/comments", response_model=list[IssueComment])
async def list_issue_comments(
    issue_id: str, submission_store: SubmissionStore = Depends(get_submission_store),
    conference_store: ConferenceStore = Depends(get_conference_store),
    issue_store: IssueStore = Depends(get_issue_store), current_user_id: str = Depends(get_current_user_id),
):
    _, paper = _issue(issue_id, current_user_id, issue_store, conference_store, submission_store)
    reviewers = {a.reviewer_id for a in submission_store.list_assignments(paper.submission_id)}
    return [comment.model_copy(update={"author_id": "Reviewer"})
            if comment.author_id in reviewers and comment.author_id != current_user_id
            and not paper_chair(paper, current_user_id, conference_store, submission_store) else comment
            for comment in issue_store.get_comments(issue_id)]
