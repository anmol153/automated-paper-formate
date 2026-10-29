"""Formal review confidentiality, revision/form binding, release and decision guards."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.api import review_routes
from app.models.conference import ConferenceRole

from .test_phase1_security import PAPER, password_hash, world  # noqa: F401
from .test_phase2_revisions import create_paper, upload
from .test_phase3_collaboration import assign, move


FORM={"name":"Test review","criteria":[
    {"id":"quality","label":"Technical quality","kind":"score","minimum":1,"maximum":5},
    {"id":"summary","label":"Author-visible comments","kind":"text"},
    {"id":"confidence","label":"Chair-only confidence","kind":"score","visibility":"chairs"}],
    "recommendations":["Accept","Reject","Major Revision"]}


def configure(w, **changes):
    chair=w.client("chair")
    url=f"/api/v1/conferences/{w.conf.conference_id}/review-configuration"
    existing=chair.get(url).json()
    body={"expected_version":existing["version"],"form":changes.pop("form",FORM),"policy":{**existing["policy"],**changes}}
    result=chair.put(url,json=body)
    assert result.status_code==200,result.text
    return result.json()


def setup(w):
    base,first=create_paper(w)
    config=configure(w)
    assignment=assign(w,base)
    payload={"assignment_id":assignment["assignment_id"],"revision_id":first["revision_id"],"form_id":config["form_id"],
             "expected_version":0,"submit":False,"recommendation":"Accept","answers":{"quality":4,"summary":"Public review comments","confidence":3},
             "confidential_comments":"Private chair comments"}
    return base,first,payload


def save(w,base,payload):
    return w.client("reviewer").put(base+"/reviews/mine",json=payload)


def release(w,base,revision):
    return w.client("chair").post(base+"/reviews/release",json={"expected_revision_id":revision["revision_id"]})


def test_drafts_private_submissions_chair_visible_and_release_public_projection(world):
    w=world
    base,first,payload=setup(w)
    draft=save(w,base,payload)
    assert draft.status_code==200,draft.text
    rid=draft.json()["review_id"]
    assert w.client("author").get(base+"/reviews").json()["reviews"]==[]
    chair=w.client("chair").get(base+"/reviews").json()
    assert chair["progress"]["missing"]==1 and chair["progress"]["submitted"]==0
    assert "answers" not in chair["reviews"][0] and "confidential_comments" not in chair["reviews"][0]
    assert w.client("chair").get(base+f"/reviews/{rid}/history").json()==[]
    payload.update(expected_version=1,submit=True)
    submitted=save(w,base,payload)
    assert submitted.status_code==200,submitted.text
    chair=w.client("chair").get(base+"/reviews").json()
    assert chair["reviews"][0]["confidential_comments"]=="Private chair comments"
    assert chair["progress"]["submitted"]==1
    assert w.client("author").get(base+"/reviews").json()["reviews"]==[]
    assert release(w,base,first).json()["released"]==1
    assert release(w,base,first).json()["released"]==0
    public=w.client("author").get(base+"/reviews").json()["reviews"][0]
    assert public["reviewer_id"]=="Reviewer" and public["answers"]=={"quality":4,"summary":"Public review comments"}
    assert "confidential_comments" not in public and "confidence" not in str(public)
    assert len(w.client("author").get(base+f"/reviews/{rid}/history").json())==1
    assert w.client("author").post(base+"/reviews/release",json={"expected_revision_id":first["revision_id"]}).status_code==403


def test_released_versions_remain_fixed_while_reviewer_edits(world):
    w=world
    base,first,payload=setup(w)
    payload["submit"]=True
    initial=save(w,base,payload).json()
    release(w,base,first)
    public=w.client("author").get(base+"/reviews").json()["reviews"][0]
    payload.update(expected_version=1,submit=False,answers={"quality":1,"summary":"New private draft","confidence":2})
    assert save(w,base,payload).status_code==200
    assert w.client("author").get(base+"/reviews").json()["reviews"][0]==public
    assert w.client("chair").get(base+"/reviews").json()["progress"]["submitted"]==0
    payload.update(expected_version=2,submit=True)
    assert save(w,base,payload).status_code==200
    assert w.client("author").get(base+"/reviews").json()["reviews"][0]==public
    release(w,base,first)
    history=w.client("author").get(base+f"/reviews/{initial['review_id']}/history").json()
    assert [v["version"] for v in history]==[3,1]
    assert history[1]==public


@pytest.mark.parametrize("change",[
    {"answers":{"quality":6,"summary":"Text","confidence":3},"submit":True},
    {"answers":{"quality":"4","summary":"Text","confidence":3},"submit":True},
    {"answers":{"quality":True}},
    {"answers":{"unknown":4}},
    {"answers":{"quality":4},"submit":True},
    {"recommendation":"Unconfigured label","submit":True},
])
def test_review_validation_rejects_wrong_scores_unknown_fields_and_missing_criteria(world,change):
    base,_,payload=setup(world)
    payload.update(change)
    assert save(world,base,payload).status_code==422
    assert world.submissions._connect().execute("SELECT COUNT(*) FROM formal_reviews").fetchone()[0]==0


def test_deadline_and_submitted_edit_policy_are_enforced(world):
    w=world
    base,_,payload=setup(w)
    configure(w,deadline=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
    assert save(w,base,payload).status_code==409
    configure(w,deadline=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),allow_edit_submitted=False)
    payload["submit"]=True
    assert save(w,base,payload).status_code==200
    payload.update(expected_version=1)
    assert save(w,base,payload).status_code==409
    configure(w,allow_edit_submitted=True,deadline=None)
    assert save(w,base,payload).status_code==200


def test_existing_reviews_keep_form_snapshot_and_stale_forms_conflict(world):
    w=world
    base,_,payload=setup(w)
    assert save(w,base,payload).status_code==200
    changed={**FORM,"name":"New form","criteria":[{"id":"new_question","label":"New question","kind":"text"}]}
    newer=configure(w,form=changed)
    assert newer["form_id"]!=payload["form_id"]
    payload.update(expected_version=1,submit=True)
    result=save(w,base,payload)
    assert result.status_code==200 and result.json()["form_id"]==payload["form_id"]
    assert result.json()["form"]["name"]=="Test review"
    w.client("chair").post(base+"/review",json="unassigned")
    other={**payload,"assignment_id":w.submissions.list_assignments(base.rsplit('/',1)[1])[-1].assignment_id,"expected_version":0}
    assert w.client("unassigned").put(base+"/reviews/mine",json=other).status_code==409


def test_configuration_updates_use_version_checks_and_timezone_aware_deadlines(world):
    w=world
    cfg=configure(w)
    url=f"/api/v1/conferences/{w.conf.conference_id}/review-configuration"
    body={"expected_version":0,"form":FORM,"policy":cfg["policy"]}
    assert w.client("chair").put(url,json=body).status_code==409
    body["expected_version"]=cfg["version"]
    body["policy"]["deadline"]="2030-01-01T12:00:00"
    assert w.client("chair").put(url,json=body).status_code==422
    assert w.client("author").put(url,json=body).status_code in {403,422}


def test_reviews_are_revision_bound_and_decisions_require_current_reviews(world):
    w=world
    base,first,payload=setup(w)
    configure(w,minimum_reviews=1)
    assert move(w.client("chair"),base,"accepted").status_code==409
    payload["submit"]=True
    assert save(w,base,payload).status_code==200
    assert move(w.client("chair"),base,"changes_requested").status_code==200
    second=upload(w.client("author"),base,first).json()
    assert move(w.client("author"),base,"submitted").status_code==200
    assert move(w.client("chair"),base,"under_review").status_code==200
    payload["expected_version"]=1
    assert save(w,base,payload).status_code==409
    assert move(w.client("chair"),base,"accepted").status_code==409
    assert release(w,base,first).status_code==409
    payload.update(revision_id=second["revision_id"],expected_version=0)
    submitted=save(w,base,payload)
    assert submitted.status_code==200,submitted.text
    assert move(w.client("chair"),base,"accepted",reason="Accepted based on current review").status_code==200
    decision=w.client("author").get(base+"/reviews").json()["decision"]
    assert decision["revision_id"]==second["revision_id"] and decision["decision"]=="accepted"
    rows=w.submissions._connect().execute("SELECT review_id,version FROM decision_reviews").fetchall()
    assert [(r[0],r[1]) for r in rows]==[(submitted.json()["review_id"],1)]


def test_conflict_revokes_access_blocks_assignment_and_needs_explicit_reassignment(world):
    w=world
    base,first,payload=setup(w)
    response=w.client("reviewer").post(f"/api/v1/reviewer/assignments/{payload['assignment_id']}/conflict",json={"reason":"Recent collaborator"})
    assert response.status_code==201,response.text
    cid=response.json()["conflict_id"]
    assert w.client("reviewer").get(base+"/reviews").status_code==404
    assert w.client("reviewer").get(base+"/file").status_code==404
    assert w.client("chair").post(base+"/review",json="reviewer").status_code==409
    assert w.client("author").get(base+"/conflicts").status_code==403
    activity=w.client("author").get(base+"/activity").json()["events"]
    assert not any("conflict" in e["action"] for e in activity)
    workspace=w.client("reviewer").get("/api/v1/reviewer/workspace").json()
    assert not any(a["submission_id"]==base.rsplit('/',1)[1] for a in workspace["assignments"])
    assert workspace["conflicts"][0]["conflict_id"]==cid
    withdrawn=w.client("reviewer").post(f"/api/v1/reviewer/conflicts/{cid}/withdraw",json={"expected_version":1,"reason":"Recorded against wrong paper"})
    assert withdrawn.status_code==200 and not withdrawn.json()["assignment_restored"]
    assert w.client("reviewer").get(base).status_code==404
    assign(w,base)
    assert w.client("reviewer").get(base+"/reviews").status_code==200


def test_author_chair_cannot_access_private_reviews_or_decide_own_paper(world):
    w=world
    base,first,payload=setup(w)
    payload["submit"]=True
    save(w,base,payload)
    issue=w.issues.list_by_submission(base.rsplit('/',1)[1])[0]
    assert w.client("chair").patch("/api/v1/issues/"+issue.issue_id,json={"assignee_id":"reviewer"}).status_code==200
    # Promote the submitting author to chair: paper-level recusal still applies.
    w.conferences.add_member(w.conf.conference_id,"author",ConferenceRole.OWNER)
    view=w.client("author").get(base+"/reviews").json()
    assert not view["is_chair"] and view["reviews"]==[] and view["progress"] is None
    assert w.client("author").get(base+"/workflow").json()["assignments"]==[]
    assert w.client("author").get("/api/v1/issues/"+issue.issue_id).json()["assignee_id"] is None
    assert move(w.client("author"),base,"accepted").status_code==403
    assert w.client("author").post(base+"/reviews/release",json={"expected_revision_id":first["revision_id"]}).status_code==403
    assert w.client("author").post(base+"/conversation",json={"body":"Bypass","visibility":"chairs"}).status_code==403


def test_release_identity_policy_is_snapshotted_and_does_not_unmask_old_releases(world):
    w=world
    base,first,payload=setup(w)
    payload["submit"]=True
    save(w,base,payload)
    release(w,base,first)
    configure(w,reviewer_identities="visible",publish_recommendation=False)
    public=w.client("author").get(base+"/reviews").json()["reviews"][0]
    assert public["reviewer_id"]=="Reviewer" and public["recommendation"]=="Accept"
    payload.update(expected_version=1)
    save(w,base,payload)
    release(w,base,first)
    public=w.client("author").get(base+"/reviews").json()["reviews"][0]
    assert public["reviewer_id"]=="reviewer" and public["recommendation"] is None


def test_peer_reviews_are_hidden_until_configured_and_own_review_submitted(world):
    w=world
    base,_,payload=setup(w)
    payload["submit"]=True
    first=save(w,base,payload).json()
    second_assignment=w.client("chair").post(base+"/review",json="unassigned").json()
    peer=w.client("unassigned")
    assert peer.get(base+"/reviews").json()["reviews"]==[]
    configure(w,reviewers_see_others=True)
    assert peer.get(base+"/reviews").json()["reviews"]==[]
    other={**payload,"assignment_id":second_assignment["assignment_id"]}
    assert peer.put(base+"/reviews/mine",json=other).status_code==200
    visible=peer.get(base+"/reviews").json()["reviews"]
    first_view=next(r for r in visible if r["review_id"]==first["review_id"])
    assert first_view["reviewer_id"]=="Reviewer" and "confidential_comments" not in first_view and "confidence" not in str(first_view)


@pytest.mark.parametrize("actor",["other","unassigned","outsider"])
def test_review_endpoints_hide_unrelated_papers(world,actor):
    base,first,payload=setup(world)
    client=world.client(actor)
    assert client.get(base+"/reviews").status_code==404
    assert client.put(base+"/reviews/mine",json=payload).status_code==404
    assert client.get(base+"/conflicts").status_code==404
    assert client.post(base+"/reviews/release",json={"expected_revision_id":first["revision_id"]}).status_code==404


def test_form_review_release_and_decision_snapshots_are_immutable(world):
    w=world
    base,first,payload=setup(w)
    payload["submit"]=True
    save(w,base,payload);release(w,base,first)
    assert move(w.client("chair"),base,"accepted").status_code==200
    for statement in ["UPDATE review_forms SET form_json='{}'","DELETE FROM review_versions","DELETE FROM review_releases","DELETE FROM paper_decisions","DELETE FROM decision_reviews","UPDATE formal_reviews SET revision_id='other'"]:
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):
            w.submissions._connect().execute(statement)


def test_concurrent_review_saves_have_one_winner(world):
    w=world
    base,_,payload=setup(w)
    client=w.client("reviewer")
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls=[pool.submit(client.put,base+"/reviews/mine",json={**payload,"recommendation":recommendation}) for recommendation in ["Accept","Reject"]]
        results=[call.result(timeout=20) for call in calls]
    assert sorted(r.status_code for r in results)==[200,409]
    assert w.submissions._connect().execute("SELECT COUNT(*) FROM review_versions").fetchone()[0]==1


def test_private_review_notifications_disappear_when_chair_role_changes(world):
    w=world
    base,_,payload=setup(w)
    payload["submit"]=True
    save(w,base,payload)
    chair=w.client("chair")
    assert any(n["title"]=="Formal review submitted" for n in chair.get("/api/v1/notifications").json())
    w.conferences.add_member(w.conf.conference_id,"chair",ConferenceRole.AUTHOR)
    assert not any(n["title"]=="Formal review submitted" for n in chair.get("/api/v1/notifications").json())


def test_review_and_notification_writes_roll_back_together(world,monkeypatch):
    w=world
    base,_,payload=setup(w)
    def fail(*args):
        raise sqlite3.OperationalError("Notification failure")
    monkeypatch.setattr(review_routes,"notify_chairs",fail)
    from fastapi.testclient import TestClient
    with TestClient(w.app,base_url="https://testserver",raise_server_exceptions=False) as client:
        client.headers["Authorization"]=w.client("reviewer").headers["Authorization"]
        response=client.put(base+"/reviews/mine",json={**payload,"submit":True})
    assert response.status_code==500
    assert w.submissions._connect().execute("SELECT COUNT(*) FROM formal_reviews").fetchone()[0]==0


def test_review_save_throttle_preserves_saved_versions(world):
    w=world
    base,_,payload=setup(w)
    assert save(w,base,payload).status_code==200
    from app.auth import digest
    w.users._connect().execute("UPDATE request_limits SET attempts=60 WHERE bucket=?",(digest("formal-review-save:reviewer"),))
    result=save(w,base,{**payload,"expected_version":1})
    assert result.status_code==429,result.text
    assert w.submissions._connect().execute("SELECT COUNT(*) FROM review_versions").fetchone()[0]==1


def test_recused_chair_cannot_read_private_reviews_or_self_resolve_through_chair_route(world):
    w=world
    base,first,payload=setup(w)
    save(w,base,{**payload,"submit":True})
    conflict=w.client("chair").post(base+"/conflicts",json={"reviewer_id":"chair","reason":"Institutional conflict"})
    assert conflict.status_code==201,conflict.text
    cid=conflict.json()["conflict_id"]
    view=w.client("chair").get(base+"/reviews").json()
    assert view["reviews"]==[] and view["progress"] is None and not view["is_chair"]
    assert release(w,base,first).status_code==403
    assert move(w.client("chair"),base,"accepted").status_code==403
    assert w.client("chair").patch(base+f"/conflicts/{cid}",json={"expected_version":1,"reason":"Self override"}).status_code==403


def test_reassigned_reviewer_can_read_own_history_without_unlocking_peer_reviews(world):
    w=world
    base,_,payload=setup(w)
    first=save(w,base,{**payload,"submit":True}).json()
    peer_assignment=w.client("chair").post(base+"/review",json="unassigned").json()
    peer=w.client("unassigned").put(base+"/reviews/mine",json={**payload,"assignment_id":peer_assignment["assignment_id"],"submit":True}).json()
    configure(w,reviewers_see_others=True)
    w.client("chair").delete(base+"/assignments/"+payload["assignment_id"])
    assignment=assign(w,base)
    view=w.client("reviewer").get(base+"/reviews").json()
    assert view["own_review"] is None and view["assignment_id"]==assignment["assignment_id"]
    assert any(r["review_id"]==first["review_id"] for r in view["reviews"])
    assert not any(r["review_id"]==peer["review_id"] for r in view["reviews"])
    assert w.client("reviewer").get(base+f"/reviews/{first['review_id']}/history").status_code==200


def test_chair_dashboard_omits_authored_papers_and_requires_chair_membership(world):
    w=world
    base,_,_=setup(w)
    url=f"/api/v1/conferences/{w.conf.conference_id}/review-progress"
    assert w.client("author").get(url).status_code==403
    assert any(p["submission_id"]==base.rsplit('/',1)[1] for p in w.client("chair").get(url).json()["papers"])
    w.conferences.add_member(w.conf.conference_id,"author",ConferenceRole.OWNER)
    assert not any(p["submission_id"]==base.rsplit('/',1)[1] for p in w.client("author").get(url).json()["papers"])


def test_chair_can_assign_self_draft_and_submit_a_formal_review(world):
    w = world
    base, first, payload = setup(w)
    chair = w.client("chair")
    assigned = chair.post(base + "/review", json="chair")
    assert assigned.status_code == 201, assigned.text
    own_assignment = assigned.json()["assignment_id"]
    assert chair.post(base + "/review", json="chair").status_code == 409
    details = chair.get(base + "/reviews").json()
    assert details["is_chair"] and details["can_review"]
    assert details["assignment_id"] == own_assignment
    payload.update(assignment_id=own_assignment, confidential_comments="Chair's private draft")
    draft = chair.put(base + "/reviews/mine", json=payload)
    assert draft.status_code == 200, draft.text
    assert draft.json()["state"] == "draft"
    assert chair.get(base + "/reviews").json()["own_review"]["confidential_comments"] == "Chair's private draft"
    assert w.client("author").get(base + "/reviews").json()["reviews"] == []
    assert w.client("reviewer").get(base + "/reviews").json()["reviews"] == []
    workspace = chair.get("/api/v1/reviewer/workspace").json()
    own_paper = next(row for row in workspace["assignments"] if row["assignment_id"] == own_assignment)
    assert own_paper["review_state"] == "draft"
    payload.update(expected_version=1, submit=True)
    submitted = chair.put(base + "/reviews/mine", json=payload)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "submitted"
    assert chair.get(base + "/reviews").json()["progress"]["submitted"] == 1
    assert next(row for row in chair.get("/api/v1/reviewer/workspace").json()["assignments"] if row["assignment_id"] == own_assignment)["review_state"] == "submitted"
    assert release(w, base, first).json()["released"] == 1
    public = w.client("author").get(base + "/reviews").json()["reviews"][0]
    assert public["reviewer_id"] == "Reviewer"
    assert "confidential_comments" not in public


def test_chair_review_conflict_revokes_assignment_and_prevents_further_reviews(world):
    w = world
    base, _, payload = setup(w)
    chair = w.client("chair")
    assignment = chair.post(base + "/review", json="chair").json()
    payload["assignment_id"] = assignment["assignment_id"]
    assert chair.put(base + "/reviews/mine", json=payload).status_code == 200
    conflict = chair.post(f"/api/v1/reviewer/assignments/{assignment['assignment_id']}/conflict", json={"reason": "I collaborated with an author."})
    assert conflict.status_code == 201, conflict.text
    details = chair.get(base + "/reviews").json()
    assert not details["can_review"] and details["assignment_id"] is None
    assert chair.put(base + "/reviews/mine", json={**payload, "expected_version": 1, "submit": True}).status_code == 403
    assert chair.post(base + "/review", json="chair").status_code == 403
    assert not any(row["assignment_id"] == assignment["assignment_id"] for row in chair.get("/api/v1/reviewer/workspace").json()["assignments"])
    w.conferences.add_member(w.conf.conference_id, "unassigned", ConferenceRole.OWNER)
    assert w.client("unassigned").post(base + "/review", json="chair").status_code == 409


def test_chair_role_does_not_allow_self_review_of_an_authored_paper(world):
    w = world
    base, _, payload = setup(w)
    w.conferences.add_member(w.conf.conference_id, "author", ConferenceRole.OWNER)
    assert w.client("author").post(base + "/review", json="author").status_code == 403
    assert w.client("chair").post(base + "/review", json="author").status_code == 409
    assert w.client("author").put(base + "/reviews/mine", json=payload).status_code == 403
    assert not w.client("author").get(base + "/reviews").json()["can_review"]
