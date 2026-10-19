"""Formal review configuration, drafting, release, progress and conflict workflows."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from app.api.submission_routes import _load, _member
from app.auth import get_current_user_id, limit_requests
from app.dependencies import get_conference_store, get_notification_store, get_submission_store
from app.models.notification import NotificationType
from app.models.review import ConfigureReviews, DeclareConflict, Payload, ReleaseReviews, ResolveConflict, ReviewPolicy, SaveReview
from app.security.notifications import notify
from app.security.permissions import is_chair
from app.services import reviews
from app.storage import revisions
from app.storage.database import transaction

router=APIRouter(prefix="/api/v1",tags=["formal reviews"])


class ConflictReason(Payload):
    reason: str = Field(min_length=1,max_length=4000)


def paper_for(id, actor, conferences, store):
    paper=_load(id,actor,conferences,store)
    reviews.require_reviews(store)
    return paper


def notify_chairs(notifications,store,conferences,paper,actor,title):
    for member in conferences.list_members(paper.conference_id):
        if member.user_id==actor or not reviews.can_chair(store,conferences,paper,member.user_id):
            continue
        active=store._connect().execute("SELECT 1 FROM users WHERE user_id=? AND is_active=1",(member.user_id,)).fetchone()
        if active:
            notification=notifications.create(member.user_id,NotificationType.SUBMISSION_UPDATE,title,"An update is available in the chair review workspace",related_id=paper.submission_id)
            store._connect().execute("INSERT INTO review_private_notifications VALUES (?)",(notification.notification_id,))


@router.get("/conferences/{conf_id}/review-configuration")
async def get_configuration(conf_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _member(conf_id,actor,conferences)
    result=reviews.configuration(store,conf_id)
    result["can_configure"]=is_chair(conferences,conf_id,actor)
    return result


@router.put("/conferences/{conf_id}/review-configuration")
async def configure_reviews(conf_id: str, body: ConfigureReviews, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences):
        _member(conf_id,actor,conferences)
        if not is_chair(conferences,conf_id,actor):
            raise HTTPException(status_code=403,detail="Conference chair permission required")
        result=reviews.configure(store,conf_id,actor,body.form,body.policy,body.expected_version)
    return {**result,"can_configure":True}


@router.get("/submissions/{submission_id}/reviews")
async def list_reviews(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper=paper_for(submission_id,actor,conferences,store)
    chair=reviews.can_chair(store,conferences,paper,actor)
    assignment=reviews.valid_assignment(store,paper,actor)
    config=reviews.configuration(store,paper.conference_id)
    current=revisions.latest(store,submission_id)
    rows=store._connect().execute("SELECT * FROM formal_reviews WHERE submission_id=? ORDER BY created_at",(submission_id,)).fetchall()
    output=[]
    for row in rows:
        versions=reviews.visible_versions(store,conferences,paper,row,actor)
        if versions:
            value=versions[0]
            if chair or row["reviewer_id"]==actor:
                value["latest_state"]=row["state"]
            output.append(value)
        elif chair:
            output.append({"review_id":row["review_id"],"reviewer_id":row["reviewer_id"],"revision_id":row["revision_id"],"state":"draft","latest_state":"draft","version":row["version"],"is_own":False})
    own=next((r for r in output if r["is_own"] and current and r["revision_id"]==current["revision_id"] and assignment and r.get("assignment_id")==assignment["assignment_id"]),None)
    policy=ReviewPolicy.model_validate(config["policy"])
    from app.services.intake import review_phase_open
    can_review=bool(review_phase_open(store,paper.conference_id) and assignment and current and config["form_id"] and paper.status.value=="under_review" and
                    (not policy.deadline or datetime.now(timezone.utc)<=policy.deadline) and
                    (not own or own["state"]!="submitted" or policy.allow_edit_submitted))
    decision=store._connect().execute("SELECT decision,reason,revision_id,decided_at FROM paper_decisions WHERE submission_id=?",(submission_id,)).fetchone()
    return {"reviews":output,"is_chair":chair,"can_review":can_review,"own_review":own,"decision":dict(decision) if decision else None,
            "assignment_id":assignment["assignment_id"] if assignment else None,
            "revision_id":current["revision_id"] if current else None,
            "configuration":config if chair or assignment else None,
            "progress":reviews.progress(store,paper) if chair else None}


@router.get("/submissions/{submission_id}/reviews/{review_id}/history")
async def review_history(submission_id: str, review_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper=paper_for(submission_id,actor,conferences,store)
    row=store._connect().execute("SELECT * FROM formal_reviews WHERE submission_id=? AND review_id=?",(submission_id,review_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404,detail="Review not found")
    result=reviews.visible_versions(store,conferences,paper,row,actor)
    if not result and not reviews.can_chair(store,conferences,paper,actor):
        raise HTTPException(status_code=404,detail="Review not found")
    return result


@router.put("/submissions/{submission_id}/reviews/mine")
async def save_review(submission_id: str, body: SaveReview, request: Request, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    paper_for(submission_id,actor,conferences,store)
    limit_requests(request,"formal-review-save",60,3600,user_id=actor)
    with transaction(store,conferences,notifications):
        paper=paper_for(submission_id,actor,conferences,store)
        row=reviews.save(store,paper,actor,body)
        if body.submit:
            notify_chairs(notifications,store,conferences,paper,actor,"Formal review submitted")
    version=store._connect().execute("SELECT * FROM review_versions WHERE review_id=? AND version=?",(row["review_id"],row["version"])).fetchone()
    return reviews.project(store,paper,row,version,actor,private=True)


@router.post("/submissions/{submission_id}/reviews/release")
async def release_reviews(submission_id: str, body: ReleaseReviews, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences,notifications):
        paper=paper_for(submission_id,actor,conferences,store)
        reviews.require_chair(store,conferences,paper,actor)
        current=revisions.latest(store,submission_id)
        if not current or current["revision_id"]!=body.expected_revision_id:
            raise HTTPException(status_code=409,detail="A newer revision exists; reload before releasing reviews")
        if paper.status.value=="withdrawn":
            raise HTTPException(status_code=409,detail="Withdrawn papers cannot release new reviews")
        config=reviews.configuration(store,paper.conference_id)
        rows=store._connect().execute("SELECT * FROM formal_reviews WHERE submission_id=? AND revision_id=? AND state='submitted'",(submission_id,current["revision_id"])).fetchall()
        released=0
        for row in rows:
            if not reviews.valid_assignment(store,paper,row["reviewer_id"],row["assignment_id"]):
                continue
            changed=store._connect().execute("INSERT OR IGNORE INTO review_releases VALUES (?,?,?,?,?,?,?,?)",
                ("release-"+uuid4().hex,submission_id,row["review_id"],row["version"],int(config["policy"]["reviewer_identities"]=="visible"),int(config["policy"]["publish_recommendation"]),actor,reviews.now())).rowcount
            released+=changed
        if released:
            store.audit(actor,"reviews.released",submission_id,revision_id=current["revision_id"],details={"count":released})
            notify(notifications,store,conferences,paper,actor,NotificationType.SUBMISSION_UPDATE,"Formal reviews released to authors")
    return {"released":released,"revision_id":body.expected_revision_id}


def declare_conflict(store,conferences,paper,actor,reviewer,reason):
    if not reason.strip():
        raise HTTPException(status_code=422,detail="A conflict reason is required")
    if store._connect().execute("SELECT 1 FROM review_conflicts WHERE submission_id=? AND reviewer_id=? AND resolved_at IS NULL",(paper.submission_id,reviewer)).fetchone():
        raise HTTPException(status_code=409,detail="An active conflict is already recorded")
    eligible=store._connect().execute("SELECT 1 FROM users u JOIN conference_members m ON m.user_id=u.user_id WHERE u.user_id=? AND u.is_active=1 AND m.conference_id=?",(reviewer,paper.conference_id)).fetchone()
    if not eligible:
        raise HTTPException(status_code=400,detail="Reviewer must be an active conference member")
    cid="conflict-"+uuid4().hex
    store._connect().execute("INSERT INTO review_conflicts(conflict_id,submission_id,reviewer_id,reason,declared_by,created_at) VALUES (?,?,?,?,?,?)",(cid,paper.submission_id,reviewer,reason,actor,reviews.now()))
    store._connect().execute("UPDATE review_assignments SET status='revoked' WHERE submission_id=? AND reviewer_id=? AND status IN ('pending','accepted','completed')",(paper.submission_id,reviewer))
    replacement=store._connect().execute("SELECT reviewer_id FROM review_assignments WHERE submission_id=? AND status IN ('pending','accepted','completed') ORDER BY assigned_at LIMIT 1",(paper.submission_id,)).fetchone()
    store._connect().execute("UPDATE submissions SET reviewer_id=? WHERE submission_id=?",(replacement[0] if replacement else None,paper.submission_id))
    store.audit(actor,"reviewer.conflict_declared",paper.submission_id,visibility="chairs")
    return dict(store._connect().execute("SELECT * FROM review_conflicts WHERE conflict_id=?",(cid,)).fetchone())


@router.get("/submissions/{submission_id}/conflicts")
async def list_conflicts(submission_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    paper=paper_for(submission_id,actor,conferences,store)
    reviews.require_chair(store,conferences,paper,actor)
    return [dict(r) for r in store._connect().execute("SELECT * FROM review_conflicts WHERE submission_id=? ORDER BY created_at",(submission_id,))]


@router.post("/submissions/{submission_id}/conflicts",status_code=201)
async def create_conflict(submission_id: str, body: DeclareConflict, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences,notifications):
        paper=paper_for(submission_id,actor,conferences,store)
        reviews.require_chair(store,conferences,paper,actor)
        result=declare_conflict(store,conferences,paper,actor,body.reviewer_id,body.reason)
        notify_chairs(notifications,store,conferences,paper,actor,"Review conflict needs attention")
    return result


def resolve_conflict(store,paper,actor,row,body):
    if row is None or row["resolved_at"]:
        raise HTTPException(status_code=404,detail="Active conflict not found")
    if row["version"]!=body.expected_version:
        raise HTTPException(status_code=409,detail="Conflict changed; reload before resolving")
    if not body.reason.strip():
        raise HTTPException(status_code=422,detail="A resolution reason is required")
    store._connect().execute("UPDATE review_conflicts SET resolved_at=?,resolved_by=?,resolution_reason=?,version=version+1 WHERE conflict_id=?",(reviews.now(),actor,body.reason,row["conflict_id"]))
    store.audit(actor,"reviewer.conflict_resolved",paper.submission_id,visibility="chairs")
    return {"resolved":True,"assignment_restored":False}


@router.patch("/submissions/{submission_id}/conflicts/{conflict_id}")
async def chair_resolve_conflict(submission_id: str, conflict_id: str, body: ResolveConflict, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences):
        paper=paper_for(submission_id,actor,conferences,store)
        reviews.require_chair(store,conferences,paper,actor)
        row=store._connect().execute("SELECT * FROM review_conflicts WHERE conflict_id=? AND submission_id=?",(conflict_id,submission_id)).fetchone()
        return resolve_conflict(store,paper,actor,row,body)


@router.post("/reviewer/assignments/{assignment_id}/conflict",status_code=201)
async def reviewer_conflict(assignment_id: str, body: ConflictReason, store=Depends(get_submission_store), conferences=Depends(get_conference_store), notifications=Depends(get_notification_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences,notifications):
        reviews.require_reviews(store)
        row=store._connect().execute("SELECT * FROM review_assignments WHERE assignment_id=? AND reviewer_id=?",(assignment_id,actor)).fetchone()
        if row is None:
            raise HTTPException(status_code=404,detail="Assignment not found")
        paper=paper_for(row["submission_id"],actor,conferences,store)
        if not reviews.valid_assignment(store,paper,actor,assignment_id):
            raise HTTPException(status_code=403,detail="An active review assignment is required")
        result=declare_conflict(store,conferences,paper,actor,actor,body.reason)
        notify_chairs(notifications,store,conferences,paper,actor,"Reviewer declared a conflict")
    return result


@router.post("/reviewer/conflicts/{conflict_id}/withdraw")
async def withdraw_conflict(conflict_id: str, body: ResolveConflict, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    with transaction(store,conferences):
        reviews.require_reviews(store)
        row=store._connect().execute("SELECT * FROM review_conflicts WHERE conflict_id=? AND reviewer_id=? AND declared_by=?",(conflict_id,actor,actor)).fetchone()
        if row is None:
            raise HTTPException(status_code=404,detail="Conflict not found")
        paper=store.get(row["submission_id"])
        _member(paper.conference_id,actor,conferences)
        return resolve_conflict(store,paper,actor,row,body)


@router.get("/reviewer/workspace")
async def reviewer_workspace(store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    reviews.require_reviews(store)
    rows=store._connect().execute("SELECT * FROM review_assignments WHERE reviewer_id=? ORDER BY assigned_at DESC",(actor,)).fetchall()
    output=[]
    for row in rows:
        paper=store.get(row["submission_id"])
        if reviews.valid_assignment(store,paper,actor,row["assignment_id"]):
            current=revisions.latest(store,paper.submission_id)
            saved=store._connect().execute("SELECT state FROM formal_reviews WHERE assignment_id=? AND revision_id=?",(row["assignment_id"],current["revision_id"] if current else None)).fetchone()
            output.append({"assignment_id":row["assignment_id"],"submission_id":paper.submission_id,"conference_id":paper.conference_id,"filename":paper.filename,"status":paper.status.value,
                "title":paper.title,"paper_number":paper.paper_number,"track_id":paper.track_id,
                "revision_id":current["revision_id"] if current else None,"review_state":saved[0] if saved else "not_started","deadline":reviews.configuration(store,paper.conference_id)["policy"]["deadline"]})
    conflicts=[dict(r) for r in store._connect().execute("SELECT c.conflict_id,c.submission_id,c.reason,c.version FROM review_conflicts c JOIN submissions s ON s.submission_id=c.submission_id JOIN conference_members m ON m.conference_id=s.conference_id AND m.user_id=c.reviewer_id WHERE c.reviewer_id=? AND c.declared_by=? AND c.resolved_at IS NULL",(actor,actor))]
    return {"assignments":output,"conflicts":conflicts}


@router.get("/conferences/{conf_id}/review-progress")
async def conference_review_progress(conf_id: str, store=Depends(get_submission_store), conferences=Depends(get_conference_store), actor=Depends(get_current_user_id)):
    _member(conf_id,actor,conferences)
    reviews.require_reviews(store)
    if not is_chair(conferences,conf_id,actor):
        raise HTTPException(status_code=403,detail="Conference chair permission required")
    rows=[]
    for paper in store.list_by_conference(conf_id):
        if reviews.can_chair(store,conferences,paper,actor):
            rows.append({"submission_id":paper.submission_id,"filename":paper.filename,"title":paper.title,"paper_number":paper.paper_number,"track_id":paper.track_id,"status":paper.status.value,**reviews.progress(store,paper)})
    return {"papers":rows,"minimum_reviews":reviews.configuration(store,conf_id)["policy"]["minimum_reviews"]}
