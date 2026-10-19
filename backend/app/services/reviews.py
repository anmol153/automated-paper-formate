"""Revision-bound formal reviews with immutable forms, versions and release snapshots."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.models.review import ReviewForm, ReviewPolicy, default_form
from app.security.permissions import is_chair
from app.storage import revisions
from app.storage.database import MigrationRequired

ACTIVE = ("pending", "accepted", "completed")


def now():
    return datetime.now(timezone.utc).isoformat()


def available(store):
    return bool(store._connect().execute("SELECT 1 FROM schema_migrations WHERE version=5").fetchone())


def require_reviews(store):
    if not available(store):
        raise MigrationRequired("Formal reviews require the explicit Phase 4 copy upgrade; see PHASE4.md")


def author(store, paper_id, actor):
    return bool(store._connect().execute("SELECT 1 FROM submission_security WHERE submission_id=? AND submitter_id=?", (paper_id,actor)).fetchone() or
                store._connect().execute("SELECT 1 FROM submission_collaborators WHERE submission_id=? AND user_id=?", (paper_id,actor)).fetchone())


def conflicted(store, paper_id, actor):
    return available(store) and bool(store._connect().execute("SELECT 1 FROM review_conflicts WHERE submission_id=? AND reviewer_id=? AND resolved_at IS NULL", (paper_id,actor)).fetchone())


def can_chair(store, conferences, paper, actor):
    return is_chair(conferences,paper.conference_id,actor) and (not available(store) or
        (not author(store,paper.submission_id,actor) and not conflicted(store,paper.submission_id,actor)))


def require_chair(store, conferences, paper, actor):
    if not can_chair(store,conferences,paper,actor):
        raise HTTPException(status_code=403, detail="An unconflicted chair who is not a paper author is required")


def configuration(store, conference_id):
    require_reviews(store)
    row = store._connect().execute("SELECT * FROM conference_review_policy WHERE conference_id=?", (conference_id,)).fetchone()
    if row:
        form = store._connect().execute("SELECT * FROM review_forms WHERE form_id=?", (row["form_id"],)).fetchone()
        return {"version":row["version"], "form_id":row["form_id"], "form_number":form["number"],
                "form":json.loads(form["form_json"]), "policy":json.loads(row["policy_json"])}
    return {"version":0,"form_id":None,"form_number":0,"form":default_form().model_dump(mode="json"), "policy":ReviewPolicy().model_dump(mode="json")}


def configure(store, conf_id, actor, form, policy, expected_version):
    old = configuration(store,conf_id)
    if old["version"] != expected_version:
        raise HTTPException(status_code=409, detail="Review configuration changed; reload before saving")
    form_id = old["form_id"]
    if not form_id or old["form"] != form.model_dump(mode="json"):
        form_id = "form-"+uuid4().hex
        number = store._connect().execute("SELECT COALESCE(MAX(number),0)+1 FROM review_forms WHERE conference_id=?", (conf_id,)).fetchone()[0]
        store._connect().execute("INSERT INTO review_forms VALUES (?,?,?,?,?,?)", (form_id,conf_id,number,form.model_dump_json(),actor,now()))
    store._connect().execute(
        "INSERT INTO conference_review_policy VALUES (?,?,?,?) ON CONFLICT(conference_id) DO UPDATE SET form_id=excluded.form_id,policy_json=excluded.policy_json,version=excluded.version",
        (conf_id,form_id,policy.model_dump_json(),expected_version+1),
    )
    store.audit(actor,"conference.review_configuration_changed",conf_id)
    return configuration(store,conf_id)


def ensure_configured(store, conf_id, actor):
    config = configuration(store,conf_id)
    return configure(store,conf_id,actor,default_form(),ReviewPolicy(),0) if not config["form_id"] else config


def valid_assignment(store, paper, actor, assignment_id=None):
    if author(store,paper.submission_id,actor) or conflicted(store,paper.submission_id,actor):
        return None
    sql = ("SELECT a.* FROM review_assignments a JOIN conference_members m ON m.user_id=a.reviewer_id "
           "JOIN users u ON u.user_id=m.user_id WHERE a.submission_id=? AND a.reviewer_id=? AND m.conference_id=? "
           "AND m.role IN ('reviewer','owner') AND u.is_active=1 AND a.status IN ('pending','accepted','completed')")
    params = [paper.submission_id,actor,paper.conference_id]
    if assignment_id:
        sql += " AND a.assignment_id=?"
        params.append(assignment_id)
    return store._connect().execute(sql+" ORDER BY a.assigned_at DESC LIMIT 1",params).fetchone()


def validate_answers(form, payload):
    fields = {f.id:f for f in form.criteria}
    if set(payload.answers)-fields.keys():
        raise HTTPException(status_code=422, detail="Review contains unknown criterion IDs")
    for key,value in payload.answers.items():
        criterion = fields[key]
        if criterion.kind == "score" and (not isinstance(value,(int,float)) or not criterion.minimum <= value <= criterion.maximum):
            raise HTTPException(status_code=422, detail=f"Score {key} must be between {criterion.minimum:g} and {criterion.maximum:g}")
        if criterion.kind == "text" and not isinstance(value,str):
            raise HTTPException(status_code=422, detail=f"Criterion {key} requires text")
    if payload.recommendation is not None and payload.recommendation not in form.recommendations:
        raise HTTPException(status_code=422, detail="Recommendation is not allowed by this review form")
    if payload.submit:
        if not payload.recommendation:
            raise HTTPException(status_code=422, detail="An overall recommendation is required")
        missing = [f.id for f in form.criteria if f.required and
                   (f.id not in payload.answers or (isinstance(payload.answers[f.id],str) and not payload.answers[f.id].strip()))]
        if missing:
            raise HTTPException(status_code=422, detail="Required review criteria are missing: "+", ".join(missing))


def save(store, paper, actor, payload):
    """Caller holds the shared transaction; reviewers can only author their own review."""
    require_reviews(store)
    from app.services.intake import require_review_phase
    require_review_phase(store, paper.conference_id)
    assignment = valid_assignment(store,paper,actor,payload.assignment_id)
    if not assignment:
        raise HTTPException(status_code=403, detail="An active, unconflicted review assignment is required")
    current = revisions.latest(store,paper.submission_id)
    if not current or current["revision_id"] != payload.revision_id:
        raise HTTPException(status_code=409, detail="The paper has a newer revision; review the current revision")
    if paper.status.value != "under_review":
        raise HTTPException(status_code=409, detail="Reviews can be saved only while the paper is under review")
    config = configuration(store,paper.conference_id)
    policy = ReviewPolicy.model_validate(config["policy"])
    if policy.deadline and datetime.now(timezone.utc)>policy.deadline:
        raise HTTPException(status_code=409, detail="The review deadline has passed; contact a chair")
    row = store._connect().execute("SELECT * FROM formal_reviews WHERE assignment_id=? AND revision_id=?", (payload.assignment_id,payload.revision_id)).fetchone()
    if (row["version"] if row else 0) != payload.expected_version:
        raise HTTPException(status_code=409, detail="Review changed; reload before saving")
    if row and row["state"] == "submitted" and not policy.allow_edit_submitted:
        raise HTTPException(status_code=409, detail="Submitted reviews are locked by conference policy")
    expected_form = row["form_id"] if row else config["form_id"]
    if not expected_form or expected_form != payload.form_id:
        raise HTTPException(status_code=409, detail="Review form changed; reload before starting this review")
    form_row = store._connect().execute("SELECT form_json FROM review_forms WHERE form_id=?", (expected_form,)).fetchone()
    form = ReviewForm.model_validate_json(form_row[0])
    validate_answers(form,payload)
    rid = row["review_id"] if row else "review-"+uuid4().hex
    version = payload.expected_version+1
    stamp = now()
    if row:
        store._connect().execute("UPDATE formal_reviews SET version=?,state=?,updated_at=? WHERE review_id=?", (version,"submitted" if payload.submit else "draft",stamp,rid))
    else:
        store._connect().execute("INSERT INTO formal_reviews VALUES (?,?,?,?,?,?,?,?,?,?)", (rid,paper.submission_id,payload.assignment_id,actor,payload.revision_id,expected_form,version,"submitted" if payload.submit else "draft",stamp,stamp))
    store._connect().execute("INSERT INTO review_versions VALUES (?,?,?,?,?,?,?)", (rid,version,payload.recommendation,json.dumps(payload.answers),payload.confidential_comments,int(payload.submit),stamp))
    store._connect().execute("UPDATE review_assignments SET status=? WHERE assignment_id=?", ("completed" if payload.submit else "accepted",payload.assignment_id))
    store.audit(actor,"formal_review.submitted" if payload.submit else "formal_review.draft_saved",paper.submission_id,visibility="chairs",revision_id=payload.revision_id)
    return store._connect().execute("SELECT * FROM formal_reviews WHERE review_id=?",(rid,)).fetchone()


def review_form(store, row):
    form = store._connect().execute("SELECT form_json FROM review_forms WHERE form_id=?",(row["form_id"],)).fetchone()
    return json.loads(form[0])


def project(store, paper, row, version, actor, *, private=False, identity_visible=False, recommendation_visible=True):
    form = review_form(store,row)
    answers = json.loads(version["answers_json"])
    if not private:
        allowed = {c["id"] for c in form["criteria"] if c["visibility"]=="authors"}
        answers = {k:v for k,v in answers.items() if k in allowed}
        form = {**form,"criteria":[c for c in form["criteria"] if c["visibility"]=="authors"]}
    result = {"review_id":row["review_id"],"revision_id":row["revision_id"],"form_id":row["form_id"],"form":form,
              "version":version["version"],"state":"submitted" if version["submitted"] else "draft",
              "reviewer_id":row["reviewer_id"] if private or identity_visible or actor==row["reviewer_id"] else "Reviewer",
              "recommendation":version["recommendation"] if recommendation_visible else None,
              "answers":answers,"created_at":version["created_at"],"is_own":actor==row["reviewer_id"],
              "assignment_active":bool(valid_assignment(store,paper,row["reviewer_id"],row["assignment_id"]))}
    if private:
        result["confidential_comments"] = version["confidential_comments"]
        result["assignment_id"] = row["assignment_id"]
    return result


def visible_versions(store, conferences, paper, row, actor):
    own = row["reviewer_id"]==actor and bool(valid_assignment(store,paper,actor))
    chair = can_chair(store,conferences,paper,actor)
    rows = store._connect().execute("SELECT * FROM review_versions WHERE review_id=? ORDER BY version DESC",(row["review_id"],)).fetchall()
    if own:
        return [project(store,paper,row,v,actor,private=True) for v in rows]
    if chair:
        return [project(store,paper,row,v,actor,private=True) for v in rows if v["submitted"]]
    config = configuration(store,paper.conference_id)
    own_submitted=any(valid_assignment(store,paper,actor,r[0]) for r in store._connect().execute(
        "SELECT assignment_id FROM formal_reviews WHERE submission_id=? AND reviewer_id=? AND revision_id=? AND state='submitted'",
        (paper.submission_id,actor,row["revision_id"])).fetchall())
    peer = (not author(store,paper.submission_id,actor) and valid_assignment(store,paper,actor) and config["policy"]["reviewers_see_others"] and own_submitted)
    result=[]
    for v in rows:
        release = store._connect().execute("SELECT * FROM review_releases WHERE review_id=? AND version=?",(row["review_id"],v["version"])).fetchone()
        if release and author(store,paper.submission_id,actor):
            value=project(store,paper,row,v,actor,identity_visible=bool(release["identities_visible"]),recommendation_visible=bool(release["publish_recommendation"]))
            value["released_at"]=release["created_at"]
            result.append(value)
        elif peer and v["submitted"] and valid_assignment(store,paper,row["reviewer_id"],row["assignment_id"]):
            result.append(project(store,paper,row,v,actor))
    return result


def progress(store, paper):
    current=revisions.latest(store,paper.submission_id)
    assignments=store.list_assignments(paper.submission_id)
    rows=[]
    for a in assignments:
        valid=bool(valid_assignment(store,paper,a.reviewer_id,a.assignment_id))
        review=store._connect().execute("SELECT review_id,state,version FROM formal_reviews WHERE assignment_id=? AND revision_id=?",(a.assignment_id,current["revision_id"] if current else None)).fetchone()
        rows.append({**a.model_dump(mode="json"),"eligible":valid,"review_state":review["state"] if review else "not_started","review_id":review["review_id"] if review else None})
    eligible={a["reviewer_id"] for a in rows if a["eligible"]}
    submitted={a["reviewer_id"] for a in rows if a["eligible"] and a["review_state"]=="submitted"}
    return {"assignments":rows,"submitted":len(submitted),
            "missing":len(eligible-submitted), "revision_id":current["revision_id"] if current else None}


def decision_guard(store, conferences, paper, actor, target):
    if not available(store):
        return
    require_chair(store,conferences,paper,actor)
    if target in {"accepted","rejected"} and not revisions.latest(store,paper.submission_id):
        raise HTTPException(status_code=409, detail="Reconcile the legacy paper revision before recording a decision")
    if target in {"accepted","rejected"} and paper.status.value == "under_review":
        minimum=configuration(store,paper.conference_id)["policy"]["minimum_reviews"]
        if progress(store,paper)["submitted"]<minimum:
            raise HTTPException(status_code=409, detail=f"At least {minimum} current-revision submitted reviews are required")


def record_decision(store,paper,actor,target,revision_id,reason):
    if not available(store):
        return
    did="decision-"+uuid4().hex
    minimum=configuration(store,paper.conference_id)["policy"]["minimum_reviews"]
    store._connect().execute("INSERT INTO paper_decisions VALUES (?,?,?,?,?,?,?,?)",(did,paper.submission_id,revision_id,target,reason,actor,now(),minimum))
    for row in store._connect().execute("SELECT * FROM formal_reviews WHERE submission_id=? AND revision_id=? AND state='submitted'",(paper.submission_id,revision_id)).fetchall():
        if valid_assignment(store,paper,row["reviewer_id"],row["assignment_id"]):
            store._connect().execute("INSERT INTO decision_reviews VALUES (?,?,?)",(did,row["review_id"],row["version"]))
